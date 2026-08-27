import logging
import time
from pathlib import Path

from sacred import Ingredient

from science_jubilee.machine_session import MachineSession
from science_jubilee.scripts.ingredients.acquisition import acquire, acquisition

logger = logging.getLogger(__name__)

scan = Ingredient("scan", ingredients=[acquisition])


@scan.config
def scan_config():
    start = [144.0, 125.0, 320.0]  # start corner [X, Y, Z] in mm
    stop = [184.0, 145.0, 220.0]  # stop corner [X, Y, Z] in mm
    steps = [20, 10, 1]  # grid size [NX, NY, NZ]
    delay = 0.5  # seconds between captures


@scan.capture
def run_scan(start, stop, steps, delay, out) -> list[str]:
    if len(start) != 3 or len(stop) != 3 or len(steps) != 3:
        raise ValueError("start, stop, and steps must contain X, Y, and Z values")
    if any(step < 1 for step in steps):
        raise ValueError("steps values must be positive")

    step_x = (stop[0] - start[0]) / max(steps[0] - 1, 1)
    step_y = (stop[1] - start[1]) / max(steps[1] - 1, 1)
    step_z = (stop[2] - start[2]) / max(steps[2] - 1, 1)
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)

    session = MachineSession.from_env(env_file=".env.hardware")
    nav = session.free_navigator
    cam = session.camera
    light = session.light

    logger.info(
        "Region (%.1f, %.1f, %.1f) -> (%.1f, %.1f, %.1f)  steps %dx%dx%d",
        start[0],
        start[1],
        start[2],
        stop[0],
        stop[1],
        stop[2],
        steps[0],
        steps[1],
        steps[2],
    )
    saved: list[str] = []
    img_idx = 0

    for h in range(steps[2]):
        z = start[2] - h * step_z
        nav.move_to(z=z)
        nav.move_to(x=start[0], y=start[1])
        for i in range(steps[0]):
            direction = 1 if i % 2 == 0 else -1
            for j in range(steps[1]):
                time.sleep(delay)
                # use grid-position index so names match physical position regardless of direction
                j_idx = j if direction == 1 else steps[1] - 1 - j
                img_idx += 1
                current_x = start[0] + i * step_x
                current_y = start[1] + j_idx * step_y
                img_name = f"img_n{img_idx}_x{current_x:g}_y{current_y:g}_z{z:g}"
                path = acquire(cam=cam, light=light, save_dir=folder, name=img_name)
                saved.append(path)
                logger.info("Captured %s", img_name)
                if j < steps[1] - 1:
                    nav.jog(y=direction * step_y)
            if i < steps[0] - 1:
                nav.jog(x=step_x)

    logger.info("Snake scan complete. Images saved to %s", folder.resolve())
    return saved
