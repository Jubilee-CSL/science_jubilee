"""
Snake-pattern image acquisition script.

Moves the camera head in a snake (boustrophedon) raster over a rectangular region,
capturing one image per step.

Usage:
    python scripts/run_snake_scan.py [--start X Y] [--stop X Y] [--steps NX NY]
                                     [--z Z] [--out FOLDER] [--delay SECONDS]
"""

import argparse
import logging
import time
from pathlib import Path

from science_jubilee.machine_session import MachineSession
from science_jubilee.navigation.free_navigation import FreeNavigator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def snake_scan(
    start_x: float,
    start_y: float,
    stop_x: float,
    stop_y: float,
    steps_x: int,
    steps_y: int,
    z: float,
    save_folder: str,
    delay: float = 0.5,
) -> None:
    step_x = (stop_x - start_x) / max(steps_x - 1, 1)
    step_y = (stop_y - start_y) / max(steps_y - 1, 1)
    out = Path(save_folder)
    out.mkdir(parents=True, exist_ok=True)

    session = MachineSession.from_env(env_file=".env.hardware")
    nav = FreeNavigator(session.motion, session.tool_changer)
    cam = session.camera

    logger.info("Region (%.1f,%.1f) → (%.1f,%.1f)  steps %dx%d  Z=%.1f",
                start_x, start_y, stop_x, stop_y, steps_x, steps_y, z)
    nav.move_to(z=z)
    nav.move_to(x=start_x, y=start_y)

    for i in range(steps_x):
        col_y = start_y if i % 2 == 0 else stop_y
        direction = 1 if i % 2 == 0 else -1
        for j in range(steps_y):
            time.sleep(delay)
            img = cam.get_image()
            name = f"snake_{i:03d}_{j:03d}"
            cam.save_image(img=img, save_name=str(out / name))
            logger.info("Captured %s", name)
            if j < steps_y - 1:
                nav.jog(y=direction * step_y)
        if i < steps_x - 1:
            nav.move_to(y=col_y)
            nav.jog(x=step_x)

    logger.info("Snake scan complete. Images saved to %s", out.resolve())


def main() -> None:
    p = argparse.ArgumentParser(description="Snake-pattern image acquisition")
    p.add_argument("--start", nargs=2, type=float, default=[144.0, 125.0],
                   metavar=("X", "Y"), help="Start corner in mm (default: 144 125)")
    p.add_argument("--stop",  nargs=2, type=float, default=[184.0, 145.0],
                   metavar=("X", "Y"), help="Stop corner in mm  (default: 184 145)")
    p.add_argument("--steps", nargs=2, type=int,   default=[20, 10],
                   metavar=("NX", "NY"), help="Grid size          (default: 20 10)")
    p.add_argument("--z",     type=float, default=320.0,
                   help="Z height in mm       (default: 320)")
    p.add_argument("--out",   default="snake_images",
                   help="Output folder        (default: snake_images)")
    p.add_argument("--delay", type=float, default=0.5,
                   help="Seconds between captures (default: 0.5)")
    args = p.parse_args()

    snake_scan(
        start_x=args.start[0], start_y=args.start[1],
        stop_x=args.stop[0],   stop_y=args.stop[1],
        steps_x=args.steps[0], steps_y=args.steps[1],
        z=args.z,
        save_folder=args.out,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()
