import pytest
import logging

logger = logging.getLogger(__name__)

@pytest.mark.invasive
def test_home_all(transport):
    try:
        logger.info("Parking any active tool (T-1)")
        transport.park_tool()
    except Exception:
        pass

    logger.info("Homing all axes via transport.home_all()")
    transport.home_all()

    homed = transport.get_axes_homed()
    logger.info("Homed state: %s", homed)

    assert homed and all(homed[:4]), f"Expected first 4 axes homed, got: {homed}"
