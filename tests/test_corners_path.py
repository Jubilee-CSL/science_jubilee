import logging
import pytest


logger = logging.getLogger(__name__)


@pytest.mark.invasive
def test_eight_corners_xy_at_two_z(motion, transport):
    """Move to the 4 XY corners at Z=0 (if within limits) and at Z=max.

    - Uses axis limits to compute corners with a small safety margin.
    - Homes axes and gates Z by deck-clear.
    - First visits the corners at Z≈0, then repeats at Z=max.
    """
    driver = motion

    # Ensure required axes exist
    letters = set(driver.get_available_axes() or [])
    required = {"X", "Y", "Z"}
    if not required.issubset(letters):
        pytest.skip(f"Required axes {required} not available: got {letters}")

    # Axis limits
    limits = driver.get_axis_limits() or {}
    for ax in ("X", "Y", "Z"):
        if ax not in limits:
            pytest.skip("Missing axis limits; cannot compute corners.")
    xmin, xmax = limits["X"]
    ymin, ymax = limits["Y"]
    zmin, zmax = limits["Z"]

    # Home sequence: park tool if U exists, home Y, X, set deck clear, then home Z
    try:
        if "U" in letters:
            logger.info("Parking any active tool")
            transport.park_tool()
    except Exception:
        pass

    logger.info("Homing X, Y, (U)")
    if "U" in letters:
        driver.home("u")
    driver.home("y")
    driver.home("x")

    # Ensure Z homing gate is open
    logger.info("Learning deck clearance: True, then homing Z")
    driver.learn_deck_clearance(True)
    driver.home("z")

    # Safety margin (absolute mm) away from hard limits
    margin = 5.0
    sxmin = xmin + margin
    sxmax = xmax - margin
    symin = ymin + margin
    symax = ymax - margin

    # Determine usable Z=0; prefer true zero if within limits, else zmin
    z0 = 0.0 if (zmin <= 0.0 <= zmax) else float(zmin)
    z_hi = float(zmax)

    corners = [
        (sxmin, symin),
        (sxmin, symax),
        (sxmax, symin),
        (sxmax, symax),
    ]

    feed = 4000.0

    print("Corners at Z≈0:")
    for (x, y) in corners:
        driver.move_to({"x": float(x), "y": float(y), "z": float(z0)}, s=feed, wait=True)
        print(f"  X:{x:.2f} Y:{y:.2f} Z:{z0:.2f}")

    print("Corners at Z=max:")
    for (x, y) in corners:
        driver.move_to({"x": float(x), "y": float(y), "z": float(z_hi)}, s=feed, wait=True)
        print(f"  X:{x:.2f} Y:{y:.2f} Z:{z_hi:.2f}")

    pos = driver.get_positions()
    logger.info("Final positions: %s", pos)
    for ax in ("X", "Y", "Z"):
        v = pos.get(ax)
        if isinstance(v, (int, float)):
            print(f"  {ax}: {float(v):.3f}")
        else:
            print(f"  {ax}: (unknown)")
