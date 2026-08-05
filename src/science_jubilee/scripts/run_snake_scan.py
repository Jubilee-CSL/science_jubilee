import logging

from sacred import Experiment
from sacred.observers import MongoObserver

from science_jubilee.scripts.config_dialog import ask_run_config
from science_jubilee.scripts.ingredients.snake_scan import run_scan, scan

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ex = Experiment("snake_scan", ingredients=[scan])
ex.observers.append(MongoObserver(db_name="jubilee26"))


@ex.config
def config():
    name = ""               # run label stored in Sacred config
    out  = "snake_images"
    scan = dict(            # noqa: F841
        start = [144.0, 125.0],
        stop  = [184.0, 145.0],
        steps = [20, 10],
        z     = 320.0,
        delay = 0.5,
    )
    acquisition = dict(     # noqa: F841
        mode    = "simple",  # "simple" | "illuminated"
        nb_leds = 8,
        debug   = False,
        led_r   = 255,
        led_g   = 255,
        led_b   = 50,
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
        z=scan_cfg["z"],
        delay=scan_cfg["delay"],
    )
    for path in saved:
        _run.add_artifact(path)


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
