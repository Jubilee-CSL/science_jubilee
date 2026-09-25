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
    start = 50.0, 50.0, 320.0
    stop = 200.0, 200.0, 220.0
    steps = 5, 5, 3
    delay = 0.5  # seconds between captures
    focus_mode = "auto"  # "manual" | "single" | "auto"/"autofocus"
    lens_position = 12  # manual-focus LensPosition value [0-12]
    autofocus_z_delay = 1.0  # auto-focus settle time after each Z move
    single_focus_seconds = 3.0  # time to keep stream alive for single autofocus


def _grid_value(start: float, step: float, index: float) -> float:
    return start + index * step


def _configure_focus(
    cam,
    nav,
    start,
    step_x: float,
    step_y: float,
    step_z: float,
    steps,
    focus_mode: str,
    lens_position: int | None,
    single_focus_seconds: float,
) -> str:
    mode = cam.normalize_focus_mode(focus_mode)

    if mode == "single":
        center_x = _grid_value(start[0], step_x, (steps[0] - 1) / 2)
        center_y = _grid_value(start[1], step_y, (steps[1] - 1) / 2)
        center_z = _grid_value(start[2], step_z, (steps[2] - 1) / 2)
        logger.info(
            "Single autofocus at scan center (%.3f, %.3f, %.3f)",
            center_x,
            center_y,
            center_z,
        )
        nav.move_to(z=center_z)
        nav.move_to(x=center_x, y=center_y)
        cam.trigger_single_autofocus(focus_seconds=single_focus_seconds)
    else:
        cam.configure_focus(
            mode,
            lens_position=lens_position if mode == "manual" else None,
        )
        if mode == "manual":
            logger.info("Manual focus set to lens position %s", lens_position)

    return mode


@scan.capture
def run_scan(
    start,
    stop,
    steps,
    delay,
    out,
    focus_mode="auto",
    lens_position=12,
    autofocus_z_delay=1.0,
    single_focus_seconds=3.0,
) -> list[str]:
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

    active_focus_mode = _configure_focus(
        cam=cam,
        nav=nav,
        start=start,
        step_x=step_x,
        step_y=step_y,
        step_z=step_z,
        steps=steps,
        focus_mode=focus_mode,
        lens_position=lens_position,
        single_focus_seconds=single_focus_seconds,
    )

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
        z = _grid_value(start[2], step_z, h)
        nav.move_to(z=z)
        if active_focus_mode == "auto" and autofocus_z_delay > 0:
            logger.info("Waiting %.2fs for autofocus after Z move", autofocus_z_delay)
            time.sleep(autofocus_z_delay)
        nav.move_to(x=start[0], y=start[1])
        for i in range(steps[0]):
            direction = 1 if i % 2 == 0 else -1
            for j in range(steps[1]):
                time.sleep(delay)
                # use grid-position index so names match physical position regardless of direction
                j_idx = j if direction == 1 else steps[1] - 1 - j
                img_idx += 1
                current_x = _grid_value(start[0], step_x, i)
                current_y = _grid_value(start[1], step_y, j_idx)
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
