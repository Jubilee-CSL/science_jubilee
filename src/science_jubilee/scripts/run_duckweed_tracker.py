"""Duckweed tracker — Sacred experiment.

Moves the camera to the target well, runs the vision pipeline to locate a
duckweed frond, then drives the inoculator to pick it up and transfer it.

    python run_duckweed_tracker.py                      # defaults + config dialog
    python run_duckweed_tracker.py with debug=False
    python run_duckweed_tracker.py print_config
"""

import logging
import time
from pathlib import Path
from typing import Iterable

import imageio.v2 as imageio
from sacred import Experiment
from sacred.observers import MongoObserver

from science_jubilee.labware.Labware import Well
from science_jubilee.machine_session import MachineSession
from science_jubilee.navigation.deck_navigation import DeckNavigator
from science_jubilee.scripts.config_dialog import ask_run_config
from science_jubilee.Vision.Duckweed_tracker.ingredients.pipeline import (
    pipeline,
    run_pipeline,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

ex = Experiment("duckweed_tracker", ingredients=[pipeline])
ex.observers.append(MongoObserver(db_name="jubilee26"))


@ex.config
def config():
    interactive = True  # True -> ask config dialog, False -> run directly from _config
    hardware = True  # True -> real hardware, False -> mock session + static image
    session_env_hardware = ".env.hardware"
    session_env_mock = ".env.mock"
    mock_image_path = (
        str(Path(__file__).resolve().parents[1])
        + "/Vision/Duckweed_tracker/Filtered_images/test_duckweed_image.png"
    )
    use_ai = False  # True -> Cellpose segmentation, False -> ExG segmentation
    inoculator_tool = 0  # tool index for the inoculator
    # labware slots (must be loaded in deck.json)
    source_slot = "0"  # reservoir slot — duckweed floats here
    dest_slot = "1"  # 24-well plate slot — transfer destination
    supplementary_offset_xyz = [
        -10.0,
        10.0,
        0,
    ]  # tool-specific machine-frame XYZ correction (mm)
    z_imaging = 200.0  # Z height for camera above reservoir centre
    image_settle = 3.0  # seconds to wait after moving before capture


def _camera_to_machine(base_xyz, cam_offset_xyz, point_xyz, supplementary_xyz):
    """Convert camera-frame point to machine frame with sign convention used by tracker."""
    bx, by, bz = base_xyz
    ox, oy, oz = cam_offset_xyz
    sx, sy, sz = supplementary_xyz
    px, py, pz = point_xyz
    return (
        float(bx + ox + px + sx),
        float(by + oy - py + sy),
        float(bz + oz - pz + sz),
    )


def _to_xyz_tuple(v: Iterable[float]):
    vals = list(v)
    if len(vals) != 3:
        raise ValueError("Expected a 3-value iterable for XYZ offset.")
    return float(vals[0]), float(vals[1]), float(vals[2])


@ex.main
def main(_config, _run):
    cfg = dict(_config)
    if cfg.get("interactive", True) and cfg.get("hardware", True):
        try:
            cfg = ask_run_config(_config, title="Duckweed tracker — configure run")
        except Exception as exc:
            logging.warning(
                "Interactive config unavailable (%s). Falling back to _config.", exc
            )
            cfg = dict(_config)

    if not cfg["hardware"]:
        logging.info("Mock mode: running with provided config.")

    env_path = (
        cfg["session_env_hardware"] if cfg["hardware"] else cfg["session_env_mock"]
    )
    session = MachineSession.from_env(env_path)
    nav: DeckNavigator = session.navigator
    if nav is None:
        raise RuntimeError(
            "No deck loaded — set JUBILEE_DECK_DEF and JUBILEE_EXPERIMENT_DIR."
        )

    cam = session.camera

    # ── 1. Resolve source well and destination wells from deck ────────────
    source_well = nav.get_well(cfg["source_slot"], "A1")  # reservoir has one well
    dest_wells = nav.get_wells_in_slot(cfg["dest_slot"])

    session.tool_changer.pickup_tool(cfg["inoculator_tool"])
    for i, dest_well_obj in enumerate(dest_wells):
        logging.info("── Well %d/%d: %s ──", i + 1, len(dest_wells), dest_well_obj.name)
        supplementary_offset = _to_xyz_tuple(cfg["supplementary_offset_xyz"])

        # ── 2. Image reservoir (camera is fixed on toolhead) ───────────────
        x_imaging = float(source_well.x)
        y_imaging = float(source_well.y - cam.offset[1])
        z_imaging = float(cfg["z_imaging"])
        cam.move_to_get_image(x_imaging, y_imaging, z_imaging)
        time.sleep(cfg["image_settle"])
        if not cfg["hardware"]:
            mock_img = imageio.imread(cfg["mock_image_path"])
            if mock_img.ndim == 3 and mock_img.shape[2] == 4:
                mock_img = mock_img[:, :, :3]
            cam._image = mock_img
            logging.info(
                "Mock mode enabled | injected image: %s", cfg["mock_image_path"]
            )
        img = cam.get_image()
        logging.info("Image acquired | shape=%s dtype=%s", img.shape, img.dtype)

        # ── 3. Vision pipeline ───────────────────────────────────────────
        duckweed_3d, float_center_3d, checkpoints_3d, img_path, debug_artifacts = (
            run_pipeline(
                img,
                cam,
                output_dir=cfg["pipeline"]["output_dir"],
                threshold_blue=cfg["float_detection"]["threshold_blue"],
                min_area_px=cfg["float_detection"]["min_area_px"],
                min_circularity=cfg["float_detection"]["min_circularity"],
                float_radius_mm=cfg["pose_estimation"]["float_radius_mm"],
                use_ai=cfg["use_ai"],
                cellpose_diameter=cfg["segmentation"]["cellpose_diameter"],
                float_width_mm=cfg["pipeline"]["float_width_mm"],
                insertion_margin_mm=cfg["pipeline"]["insertion_margin_mm"],
                target_margin_mm=cfg["pipeline"]["target_margin_mm"],
                tool_radius_mm=cfg["pipeline"]["tool_radius_mm"],
                max_offset_px=cfg["insertion_point"]["max_offset_px"],
                step_size=cfg["rrt"]["step_size"],
                max_iter=cfg["rrt"]["max_iter"],
                goal_sample_rate=cfg["rrt"]["goal_sample_rate"],
                water_level_offset_mm=cfg["pipeline"]["water_level_offset_mm"],
                debug_capture=cfg["pipeline"]["debug_capture"],
                debug_breakpoints=cfg["pipeline"]["debug_breakpoints"],
                debug_dir=cfg["pipeline"]["debug_dir"],
            )
        )
        if duckweed_3d is None:
            logging.warning(
                "No duckweed detected for well %s — skipping.", dest_well_obj.name
            )
            continue
        logging.info(
            "Pipeline outputs | duckweed_3d=%s float_center_3d=%s checkpoints=%d",
            duckweed_3d,
            float_center_3d,
            len(checkpoints_3d),
        )
        if len(checkpoints_3d) > 0:
            logging.info(
                "RRT path found successfully | checkpoints=%d",
                len(checkpoints_3d),
            )
        else:
            logging.warning("RRT path not found by pipeline.")
        if img_path:
            _run.add_artifact(img_path, name=f"img_{dest_well_obj.name}.png")
        for name, path in debug_artifacts.items():
            if name == "control":
                continue
            _run.add_artifact(path, name=f"{name}_{dest_well_obj.name}.png")

        source_well_tracking = Well(
            "A1",
            depth=70,
            totalLiquidVolume=80,
            shape="circular",
            x=float(
                x_imaging + cam.offset[0] + float_center_3d[0] + supplementary_offset[0]
            ),
            y=float(
                y_imaging + cam.offset[1] - float_center_3d[1] + supplementary_offset[1]
            ),
            z=2,
            diameter=cfg["pose_estimation"]["float_radius_mm"] * 2,
        )

        # ── 4. Convert to machine frame ──────────────────────────────────
        x_target, y_target, z_target = _camera_to_machine(
            base_xyz=(x_imaging, y_imaging, z_imaging),
            cam_offset_xyz=cam.offset,
            point_xyz=duckweed_3d,
            supplementary_xyz=supplementary_offset,
        )
        logging.info(
            "Duckweed target: x=%.2f y=%.2f z=%.2f", x_target, y_target, z_target
        )

        # ── 6. Approach and pickup sequence (checkpoint path first) ─────
        nav.move_to_well(source_well_tracking, speed_xy=500, speed_z=700)

        world_checkpoints = []
        for cp in checkpoints_3d:
            wx, wy, wz = _camera_to_machine(
                base_xyz=(x_imaging, y_imaging, z_imaging),
                cam_offset_xyz=cam.offset,
                point_xyz=cp,
                supplementary_xyz=supplementary_offset,
            )
            world_checkpoints.append((wx, wy, wz))

        if world_checkpoints:
            logging.info(
                "Executing checkpoint path with %d points.", len(world_checkpoints)
            )
            start_wx, start_wy, _ = world_checkpoints[0]
            dx_start = float(start_wx - source_well_tracking.x)
            dy_start = float(start_wy - source_well_tracking.y)
            nav.move_inside_well(
                well=source_well_tracking, dx=dx_start, dy=dy_start, speed_xy=400
            )
            nav.move_inside_well(
                well=source_well_tracking, z=z_target + 17, speed_z=200
            )
            nav.move_inside_well(well=source_well_tracking, z=z_target + 7, speed_z=100)

            prev_wx, prev_wy, _ = world_checkpoints[0]
            for wx, wy, _ in world_checkpoints[1:]:
                dx_step = float(wx - prev_wx)
                dy_step = float(wy - prev_wy)
                nav.move_inside_well(
                    well=source_well_tracking, dx=dx_step, dy=dy_step, speed_xy=200
                )
                prev_wx, prev_wy = wx, wy

            nav.move_inside_well(
                well=source_well_tracking, z=z_target + 20, speed_z=200
            )
            nav.move_inside_well(
                well=source_well_tracking, z=z_target + 70, speed_z=800
            )
        else:
            logging.warning(
                "No checkpoints generated; falling back to direct pickup routine."
            )
            dx = x_target - source_well_tracking.x
            dy = y_target - source_well_tracking.y
            nav.move_inside_well(
                well=source_well_tracking, dx=dx, dy=dy + 8, speed_xy=600
            )
            nav.move_inside_well(
                well=source_well_tracking, z=z_target + 17, speed_z=200
            )
            nav.move_inside_well(well=source_well_tracking, z=z_target + 7, speed_z=50)
            nav.move_inside_well(well=source_well_tracking, dy=-6, speed_xy=200)
            nav.move_inside_well(well=source_well_tracking, dx=+1, speed_xy=50)
            nav.move_inside_well(well=source_well_tracking, dx=-1, dy=+1, speed_xy=50)
            nav.move_inside_well(well=source_well_tracking, dy=-1, speed_xy=50)
            nav.move_inside_well(well=source_well_tracking, dx=+1, dy=-1, speed_xy=50)
            nav.move_inside_well(well=source_well_tracking, z=z_target + 20, speed_z=40)
            nav.move_inside_well(
                well=source_well_tracking, z=z_target + 40, speed_z=800
            )

        # ── 7. Deposit in destination well ───────────────────────────────
        nav.move_to_well(dest_well_obj, speed_xy=3000, speed_z=800)

        # nav.move_inside_well(well=source_well, dx=+1,        speed_xy=50)
        # nav.move_inside_well(well=source_well, dx=-1, dy=+1, speed_xy=50)
        # nav.move_inside_well(well=source_well,        dy=-1,  speed_xy=50)
        # nav.move_inside_well(well=source_well, dx=+1, dy=-1, speed_xy=50)
        nav.move_inside_well(well=dest_well_obj, dz=-2, speed_z=40)

        nav.move_inside_well(well=dest_well_obj, dz=+20, speed_z=40)
        nav.move_inside_well(well=dest_well_obj, z=200, speed_z=800)


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
