"""Sacred experiment     for the Gaussian Splatting reconstruction pipeline.

The launcher only resolves run configuration and delegates the workflow to
the reconstruction pipeline ingredient.
"""

import logging
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[2]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from sacred import Experiment
from sacred.observers import MongoObserver

from science_jubilee.scripts.config_dialog import ask_run_config
from science_jubilee.Vision.GS_Reconstruction.ingredients.pipeline import (
    pipeline,
    run_pipeline,
)


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

ex = Experiment("GS_Reconstruction", ingredients=[pipeline])
ex.observers.append(MongoObserver(db_name="jubilee26"))


@ex.config
def config():
    interactive = True
    hardware = True
    dataset_name = "Plante_2" if not hardware else "Latest_reconstruction"
    start = [110.0, 80.0, 280.0]
    stop = [250.0, 200.0, 220.0]
    steps = [5, 5, 4]
    delay = 2.0
    iterations = 7000
    run_capture = hardware
    num_photos = 100
    show = True
    pre_segment = True
    post_segment = True


@ex.main
def main(_config, _run):
    cfg = dict(_config)
    if cfg.get("interactive", True):
        try:
            cfg = ask_run_config(
                cfg,
                title="Gaussian reconstruction - configure run",
            )
        except Exception as exc:
            logging.warning(
                "Interactive config unavailable (%s). Falling back to _config.",
                exc,
            )

    run_capture = bool(cfg.get("run_capture", cfg.get("hardware", True)))
    return run_pipeline(
        dataset_name=cfg["dataset_name"],
        num_photos=cfg["num_photos"],
        iterations=cfg["iterations"],
        show=cfg["show"],
        run_capture=run_capture,
        start=cfg["start"],
        stop=cfg["stop"],
        steps=cfg["steps"],
        delay=cfg["delay"],
        pre_segment=cfg["pre_segment"],
        post_segment=cfg["post_segment"],
    )


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
