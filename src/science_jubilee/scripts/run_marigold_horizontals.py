"""Sacred experiment for the marigold horizontal targets pipeline.

The launcher only resolves run configuration and delegates the workflow to
the marigold pipeline ingredient.

Not finished
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
from science_jubilee.Vision.Marigold_Horizontal_leafs.ingredients.pipeline import (
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
   pass


@ex.main
def main(_config, _run):
    cfg = dict(_config)
    if cfg.get("interactive", True):
        try:
            cfg = ask_run_config(
                cfg,
                title="Marigold Horizontal Leafs - configure run",
            )
        except Exception as exc:
            logging.warning(
                "Interactive config unavailable (%s). Falling back to _config.",
                exc,
            )

    run_capture = bool(cfg.get("run_capture", cfg.get("hardware", True)))
    return run_pipeline(

    )


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
