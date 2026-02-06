import pytest
import logging

logger = logging.getLogger(__name__)

@pytest.mark.invasive
def test_home_xyu_and_z(motion):
    driver = motion
    # Ensure any active tool is parked to avoid homing interference on hardware
    try:
        logger.info("Parking any active tool (T-1)")
        driver.transport.send_gcode("T-1")
    except Exception:
        pass

    # Home XYU (non-interactive); Z requires deck-clear caching
    logger.info("Homing X, Y, U")
    driver.home("u")
    driver.home("y")
    driver.home("x")
    logger.info("Learning deck clearance: True, then homing Z")
    driver.learn_deck_clearance(True)
    driver.home("z")

    # Query homing status via transport convenience method
    homed = driver.transport.get_axes_homed()
    logger.info("Homed state: %s", homed)

    # Ensure at least X, Y, Z, U are homed
    assert homed and all(homed[:4]), f"Expected first 4 axes homed, got: {homed}"
