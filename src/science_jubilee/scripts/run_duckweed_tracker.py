"""Duckweed tracker — Sacred experiment.

Moves the camera to the target well, runs the vision pipeline to locate a
duckweed frond, then drives the inoculator to pick it up and transfer it.

    python run_duckweed_tracker.py                      # defaults + config dialog
    python run_duckweed_tracker.py with debug=False
    python run_duckweed_tracker.py print_config
"""

import logging
import time

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
    debug = True  # ask for confirmation before moving to target
    inoculator_tool = 0  # tool index for the inoculator
    # labware slots (must be loaded in deck.json)
    source_slot = "0"  # reservoir slot — duckweed floats here
    dest_slot = "1"  # 24-well plate slot — transfer destination
    z_imaging = 200.0  # Z height for camera above reservoir centre
    image_settle = 3.0  # seconds to wait after moving before capture


@ex.main
def main(_config, _run):
    cfg = ask_run_config(_config, title="Duckweed tracker — configure run")

    session = MachineSession.from_env(".env.hardware")
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

        # ── 2. Image reservoir (camera is fixed on toolhead) ───────────────
        cam.move_to_get_image(
            source_well.x, source_well.y - cam.offset[1], cfg["z_imaging"]
        )
        time.sleep(cfg["image_settle"])
        img = cam.get_image()
        # ── 3. Vision pipeline ───────────────────────────────────────────
        duckweed_3d, float_center_3d, img_path = run_pipeline(
            img,
            cam,
            output_dir=cfg["pipeline"]["output_dir"],
            threshold_blue=cfg["float_detection"]["threshold_blue"],
            min_area_px=cfg["float_detection"]["min_area_px"],
            min_circularity=cfg["float_detection"]["min_circularity"],
        )
        if duckweed_3d is None:
            logging.warning(
                "No duckweed detected for well %s — skipping.", dest_well_obj.name
            )
            continue
        _run.add_artifact(img_path, name=f"img_{dest_well_obj.name}.png")

        source_well = Well(
            "A1",
            depth=70,
            totalLiquidVolume=80,
            shape="circular",
            x=float(source_well.x + float_center_3d[0]),
            y=float(source_well.y - float_center_3d[1]),
            z=2,
            diameter=cfg["pose_estimation"]["float_radius_mm"] * 2,
        )

        # ── 4. Convert to machine frame ──────────────────────────────────
        ox, oy, oz = cam.offset
        x_target = float(source_well.x + ox + duckweed_3d[0])
        y_target = float(source_well.y - cam.offset[1] - duckweed_3d[1])
        z_target = float(cfg["z_imaging"] + oz - duckweed_3d[2])
        logging.info(
            "Duckweed target: x=%.2f y=%.2f z=%.2f", x_target, y_target, z_target
        )

        # ── 5. Debug confirmation ────────────────────────────────────────
        if cfg["debug"]:
            ans = input(
                f"[{dest_well_obj.name}] Confirm target ({x_target:.1f}, {y_target:.1f}, {z_target:.1f})? [y/n/q]: "
            )
            if ans.strip().lower() == "q":
                raise SystemExit("Aborted by user.")
            if ans.strip().lower() != "y":
                logging.info("Skipping well %s.", dest_well_obj.name)
                continue

        # ── 6. Approach and pickup sequence ─────────────────────────────
        dx = x_target - source_well.x
        dy = y_target - source_well.y

        nav.move_to_well(source_well, speed_xy=500, speed_z=700)
        nav.move_inside_well(well=source_well, dx=dx, dy=dy + 8, speed_xy=600)
        nav.move_inside_well(well=source_well, z=z_target + 17, speed_z=200)
        nav.move_inside_well(well=source_well, z=z_target + 7, speed_z=50)
        nav.move_inside_well(well=source_well, dy=-6, speed_xy=200)
        # 3 mm search spiral
        nav.move_inside_well(well=source_well, dx=+1, speed_xy=50)
        nav.move_inside_well(well=source_well, dx=-1, dy=+1, speed_xy=50)
        nav.move_inside_well(well=source_well, dy=-1, speed_xy=50)
        nav.move_inside_well(well=source_well, dx=+1, dy=-1, speed_xy=50)
        nav.move_inside_well(well=source_well, z=z_target + 20, speed_z=40)
        nav.move_inside_well(well=source_well, z=z_target + 40, speed_z=800)

        # ── 7. Deposit in destination well ───────────────────────────────
        nav.move_to_well(dest_well_obj, speed_xy=3000, speed_z=800)

        # nav.move_inside_well(well=source_well, dx=+1,        speed_xy=50)
        # nav.move_inside_well(well=source_well, dx=-1, dy=+1, speed_xy=50)
        # nav.move_inside_well(well=source_well,        dy=-1,  speed_xy=50)
        # nav.move_inside_well(well=source_well, dx=+1, dy=-1, speed_xy=50)
        nav.move_inside_well(well=source_well, dz=-2, speed_z=40)

        nav.move_inside_well(well=source_well, dz=+20, speed_z=40)
        nav.move_inside_well(well=source_well, z=200, speed_z=800)


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
