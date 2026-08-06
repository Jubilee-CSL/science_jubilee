"""Pick up the pen tool and draw a G-code file from the experiment directory.

    draw_deck                              # uses .env.hardware, tool 0, draw_deck.gcode
    draw_deck --tool 1
    draw_deck --gcode mark_slots.gcode
    draw_deck --env .env.mock
"""

import argparse
import sys
from pathlib import Path

from science_jubilee.machine_session import MachineSession


def run() -> None:
    parser = argparse.ArgumentParser(description="Pick up pen tool and draw from JUBILEE_EXPERIMENT_DIR.")
    parser.add_argument("--env", default=".env.hardware", help="env file to load")
    parser.add_argument("--tool", type=int, default=1, help="pen tool index")
    parser.add_argument("--gcode", default="plan_jubilee.gcode", help="G-code filename inside experiment dir")
    args = parser.parse_args()

    session = MachineSession.from_env(args.env)

    exp_dir = session.experiment_dir
    if exp_dir is None:
        sys.exit("JUBILEE_EXPERIMENT_DIR is not set — cannot locate the G-code file.")

    gcode_path = exp_dir / args.gcode
    if not gcode_path.exists():
        sys.exit(f"G-code file not found: {gcode_path}")

    nav = session.free_navigator
    print(f"Picking up tool {args.tool} ...")
    nav.pickup_tool(args.tool)

    print(f"Drawing {gcode_path} ...")
    nav.run_gcode_file(gcode_path)

    print("Parking tool ...")
    nav.park_tool()
    print("Done.")


if __name__ == "__main__":
    run()