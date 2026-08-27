"""
Illuminated acquisition test — Sacred experiment.

Captures one illuminated image (multi-LED pixel-minimum) and one simple image
at the current machine position so you can compare reflection removal.

    python run_acquisition_test.py                              # defaults + config dialog
    python run_acquisition_test.py with acquisition.nb_leds=4
    python run_acquisition_test.py print_config
"""

import logging
from pathlib import Path

from sacred import Experiment
from sacred.observers import MongoObserver

from science_jubilee.machine_session import MachineSession
from science_jubilee.scripts.config_dialog import ask_run_config
from science_jubilee.scripts.ingredients.acquisition import acquire, acquisition

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

ex = Experiment("acquisition_test", ingredients=[acquisition])
ex.observers.append(MongoObserver(db_name="jubilee26"))


@ex.config
def config():
    x = 100.0  # set in dialog before running
    compare = True  # also capture a simple image for side-by-side comparison
    acquisition = dict(  # noqa: F841
        mode="illuminated",
        nb_leds=8,
        debug=True,
        led_r=50,
        led_g=0,
        led_b=0,
    )


@ex.main
def main(_config, _run):
    cfg = ask_run_config(_config, title="Acquisition test — configure run")
    acq_cfg = cfg["acquisition"]
    folder = Path(cfg["out"])
    folder.mkdir(parents=True, exist_ok=True)

    session = MachineSession.from_env(env_file=".env.hardware")
    nav = session.free_navigator
    cam = session.camera
    light = session.light

    nav.move_to(z=cfg["z"])
    nav.move_to(x=cfg["x"], y=cfg["y"])

    illum_path = acquire(
        cam=cam,
        light=light,
        save_dir=folder,
        name="illuminated",
        mode="illuminated",
        nb_leds=acq_cfg["nb_leds"],
        debug=acq_cfg.get("debug", False),
        led_r=acq_cfg["led_r"],
        led_g=acq_cfg["led_g"],
        led_b=acq_cfg["led_b"],
    )
    _run.add_artifact(illum_path, "illuminated.jpg")

    if cfg["compare"]:
        simple_path = acquire(
            cam=cam,
            light=light,
            save_dir=folder,
            name="simple",
            mode="simple",
            nb_leds=acq_cfg["nb_leds"],
        )
        _run.add_artifact(simple_path, "simple.jpg")


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
