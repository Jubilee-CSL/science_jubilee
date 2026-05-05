import pytest
import logging

logger = logging.getLogger(__name__)

@pytest.mark.invasive
def test_home_all(motion, tool_changer):
    try:
        logger.info("Parking any active tool")
        tool_changer.park_tool()
    except Exception:
        pass

    logger.info("Homing all axes via motion.home_all()")
    motion.home_all()

    homed = motion.get_axes_homed()
    logger.info("Homed state: %s", homed)

    assert homed and all(homed[:4]), f"Expected first 4 axes homed, got: {homed}"
