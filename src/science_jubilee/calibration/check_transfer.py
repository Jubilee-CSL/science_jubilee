"""Duckweed inoculation experiment — Sacred experiment.

    python run_duckweed.py                              # defaults + config dialog
    python run_duckweed.py with tool=1 randomize=True
    python run_duckweed.py print_config
"""

import logging

from sacred import Experiment
from sacred.observers import MongoObserver

from science_jubilee.machine_session import MachineSession
from science_jubilee.scripts.config_dialog import ask_run_config
from science_jubilee.tools.unique_tools.Inoculator import Inoculator

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)

ex = Experiment("duckweed")
ex.observers.append(MongoObserver(db_name="jubilee26"))


@ex.config
def config():
    name = ""  # run label
    tool = 0  # inoculator tool index
    dest_slot = "0"  # slot whose wells are all destinations
    randomize = False  # randomize pickup position inside source well


@ex.main
def main(_config, _run):
    cfg = ask_run_config(_config, title="Duckweed — configure run")

    session = MachineSession.from_env(env_file=".env.hardware")
    nav = session.navigator
    if nav is None:
        raise RuntimeError(
            "No deck loaded — set JUBILEE_DECK_DEF and JUBILEE_EXPERIMENT_DIR."
        )

    tool_idx = cfg["tool"]
    tool = session.tool_changer.get_tool(tool_idx)
    inoculator = Inoculator(index=tool.index, name=tool.name)
    session.tool_changer.tools[tool_idx] = inoculator

    source = nav.get_well(cfg["source_slot"], cfg["source_well"])
    destination = nav.get_wells_in_slot(cfg["dest_slot"])

    session.tool_changer.pickup_tool(tool_idx)
    inoculator.transfer(nav, source, destination, randomize_pickup=cfg["randomize"])
    session.tool_changer.park_tool()


def run():
    ex.run_commandline()


if __name__ == "__main__":
    run()
