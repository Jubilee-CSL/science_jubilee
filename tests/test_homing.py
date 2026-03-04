import pytest
import logging

logger = logging.getLogger(__name__)

@pytest.mark.invasive
def test_home_all(motion):
    driver = motion
    # Ensure any active tool is parked to avoid homing interference on hardware
    try:
        logger.info("Parking any active tool (T-1)")
        driver.transport.send_gcode("T-1")
    except Exception:
        pass

    # Home all axes using firmware's canonical homing macro
    logger.info('Homing all axes via firmware macro: M98 P"homeall.g"')
    driver._gcode('M98 P"homeall.g"', wait=True)

    # Query homing status via transport convenience method
    homed = driver.transport.get_axes_homed()
    logger.info("Homed state: %s", homed)

    # Ensure at least X, Y, Z, U are homed
    assert homed and all(homed[:4]), f"Expected first 4 axes homed, got: {homed}"
