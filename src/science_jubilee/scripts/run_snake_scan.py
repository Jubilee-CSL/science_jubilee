import logging
from pathlib import Path

from sacred import Experiment
from sacred.observers import MongoObserver

from science_jubilee.scripts.config_dialog import ask_run_config
from science_jubilee.scripts.ingredients.snake_scan import run_scan, scan

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

ex = Experiment("snake_scan", ingredients=[scan])
ex.observers.append(MongoObserver(db_name="jubilee26"))


@ex.config
def config():
    name = ""  # run label stored in Sacred config
    out = "output/snake_scan"  # image output folder, editable in the run dialog
    scan = dict(  # noqa: F841
        delay=0.5,
        focus_mode="auto",  # "manual" | "single" | "auto"/"autofocus"
        lens_position=12,  # used only when focus_mode="manual"
        autofocus_z_delay=1.0,  # settle time after each Z move in auto focus
        single_focus_seconds=3.0,  # focus time for focus_mode="single"
    )
    acquisition = dict(  # noqa: F841
        mode="simple",  # "simple" | "illuminated"
        nb_leds=8,
        debug=False,
        led_r=255,
        led_g=255,
        led_b=50,
    )


@ex.main
def main(_config, _run):
    cfg = ask_run_config(_config, title="Snake scan — configure run")
    scan_cfg = cfg["scan"]
    saved = run_scan(
        out=cfg["out"],
        start=scan_cfg["start"],
        stop=scan_cfg["stop"],
        steps=scan_cfg["steps"],
        delay=scan_cfg["delay"],
        focus_mode=scan_cfg["focus_mode"],
        lens_position=scan_cfg["lens_position"],
        autofocus_z_delay=scan_cfg["autofocus_z_delay"],
        single_focus_seconds=scan_cfg["single_focus_seconds"],
    )
    for path in saved:
        _run.add_artifact(path)
        metadata_path = Path(path).with_suffix(".camera.json")
        if metadata_path.exists():
            _run.add_artifact(str(metadata_path), name=metadata_path.name)


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
