"""Capture an image, detect horizontal targets, and visit the first targets."""

import logging
import time
from pathlib import Path
from typing import Iterable

from sacred import Experiment
from sacred.observers import MongoObserver

from science_jubilee.machine_session import MachineSession
from science_jubilee.Vision.Monocular_Horizontal_leaves.ingredients.pipeline import (
    pipeline,
    run_pipeline,
)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

ex = Experiment("Marigold_horizontals", ingredients=[pipeline])
ex.observers.append(MongoObserver(db_name="jubilee26"))


@ex.config
def config():
    interactive = False
    hardware = True
    session_env_hardware = ".env.hardware"
    session_env_mock = ".env.mock"
    camera_tool = 0
    image_name = "latest.jpg"
    output_dir = str(
        Path(__file__).resolve().parents[1]
        / "Vision"
        / "Monocular_Horizontal_leaves"
        / "output"
        / "latest"
    )
    mock_image_path ="input/Mock_test.png"
    x_depart = 142.0
    y_depart = 155.0
    z_depart = 320.0
    supplementary_offset_xyz = [0.0, 0.0, -5.0]
    visit_count = 5
    xy_speed = 3000.0
    z_speed = 1000.0
    image_settle = 2.0
    run_reconstruction = False
    model = "MoGe"
    tray_z_mm = 320.0
    plant_height = None
    scale_cube = None


def _to_xyz_tuple(values: Iterable[float]) -> tuple[float, float, float]:
    values = tuple(values)
    if len(values) != 3:
        raise ValueError("supplementary_offset_xyz must contain exactly three values")
    return float(values[0]), float(values[1]), float(values[2])


def _target_to_machine_position(base_xyz, camera_offset, target_xyz, supplementary):
    base_x, base_y, base_z = base_xyz
    offset_x, offset_y, offset_z = camera_offset
    target_x, target_y, target_z = target_xyz
    supplementary_x, supplementary_y, supplementary_z = supplementary
    return (
        base_x + offset_x + target_x + supplementary_x,
        base_y + offset_y - target_y + supplementary_y,
        base_z + offset_z - target_z + supplementary_z,
    )


@ex.main
def main(_config, _run):
    cfg = dict(_config)
    env_file = cfg["session_env_hardware"] if cfg["hardware"] else cfg["session_env_mock"]
    session = MachineSession.from_env(env_file)
    camera = session.camera
    navigator = session.free_navigator
    output_dir = Path(cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    session.tool_changer.pickup_tool(cfg["camera_tool"])
    camera.move_to_get_image(cfg["x_depart"], cfg["y_depart"], cfg["z_depart"])
    if cfg["image_settle"] > 0:
        time.sleep(cfg["image_settle"])

    if not cfg["hardware"] and cfg["mock_image_path"]:
        import imageio.v2 as imageio

        mock_image = imageio.imread(cfg["mock_image_path"])
        if mock_image.ndim == 3 and mock_image.shape[2] == 4:
            mock_image = mock_image[:, :, :3]
        camera._image = mock_image

    image = camera.get_image()
    image_path = output_dir / cfg["image_name"]
    camera.save_image(img=image, save_dir=output_dir, save_name=image_path.stem)
    _run.add_artifact(image_path, name=image_path.name)

    result = run_pipeline(
        image=image,
        image_name=cfg["image_name"],
        output_dir=str(output_dir),
        run_reconstruction=cfg["run_reconstruction"],
        model=cfg["model"],
        tray_z_mm=cfg["tray_z_mm"],
        plant_height=cfg["plant_height"],
        scale_cube=cfg["scale_cube"],
        camera=camera,
        _run=_run,
    )

    targets = result.get("targets", [])
    supplementary = _to_xyz_tuple(cfg["supplementary_offset_xyz"])
    visit_count = min(int(cfg["visit_count"]), len(targets))
    logging.info("Detected %d targets; visiting %d.", len(targets), visit_count)

    for index, target in enumerate(targets[:visit_count], start=1):
        position = _target_to_machine_position(
            (cfg["x_depart"], cfg["y_depart"], cfg["z_depart"]),
            camera.offset,
            target["xyz_mm"],
            supplementary,
        )
        logging.info("Visiting target %d/%d at %s.", index, visit_count, position)
        navigator.move_to(x=position[0], y=position[1], speed=cfg["xy_speed"], wait=True)
        navigator.move_to(z=position[2], speed=cfg["z_speed"], wait=True)

    return result


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
