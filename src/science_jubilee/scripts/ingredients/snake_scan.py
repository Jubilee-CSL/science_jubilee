import logging
import time
from pathlib import Path

from sacred import Ingredient

from science_jubilee.machine_session import MachineSession
from science_jubilee.navigation.free_navigation import FreeNavigator
from science_jubilee.scripts.ingredients.acquisition import acquire, acquisition

logger = logging.getLogger(__name__)

scan = Ingredient("scan", ingredients=[acquisition])


@scan.config
def scan_config():
    start = [144.0, 125.0]  # start corner [X, Y] in mm
    stop  = [184.0, 145.0]  # stop corner  [X, Y] in mm
    steps = [20, 10]        # grid size [NX, NY]
    z     = 320.0           # Z height in mm
    delay = 0.5             # seconds between captures


@scan.capture
def run_scan(start, stop, steps, z, delay, out) -> list[str]:
    step_x = (stop[0] - start[0]) / max(steps[0] - 1, 1)
    step_y = (stop[1] - start[1]) / max(steps[1] - 1, 1)
    folder = Path(out)
    folder.mkdir(parents=True, exist_ok=True)

    session = MachineSession.from_env(env_file=".env.hardware")
    nav = FreeNavigator(session.motion, session.tool_changer)
    cam = session.camera
    light = session.light

    logger.info("Region (%.1f,%.1f) → (%.1f,%.1f)  steps %dx%d  Z=%.1f",
                start[0], start[1], stop[0], stop[1], steps[0], steps[1], z)
    nav.move_to(z=z)
    nav.move_to(x=start[0], y=start[1])

    saved: list[str] = []
    for i in range(steps[0]):
        direction = 1 if i % 2 == 0 else -1
        for j in range(steps[1]):
            time.sleep(delay)
            # use grid-position index so names match physical position regardless of direction
            j_idx = j if direction == 1 else steps[1] - 1 - j
            img_name = f"snake_{i:03d}_{j_idx:03d}"
            path = acquire(cam=cam, light=light, save_dir=folder, name=img_name)
            saved.append(path)
            logger.info("Captured %s", img_name)
            if j < steps[1] - 1:
                nav.jog(y=direction * step_y)
        if i < steps[0] - 1:
            nav.jog(x=step_x)

    logger.info("Snake scan complete. Images saved to %s", folder.resolve())
    return saved
