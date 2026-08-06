import logging
import pytest

from science_jubilee.hal.tool_changer import (
    ToolSlotError,
    ToolStateError
)
from science_jubilee.tools.Tool import Tool

logger = logging.getLogger(__name__)

# Z height that puts the carriage in range of the parking posts
_PARK_Z = 150.0

# ------------------------------------------------------------------
# Tool activation
# ------------------------------------------------------------------


@pytest.mark.invasive
def test_pickup_tool(motion, tool_changer):
    motion.move_to({"Z": _PARK_Z})
    ok = tool_changer.pickup_tool(0)

    assert ok is True
    assert tool_changer.get_active_tool_index() == 0

    tool = tool_changer.get_tool(0)
    assert tool.is_active_tool is True
    assert tool_changer.get_active_tool_index() == tool.index
    tool_changer.park_tool()


@pytest.mark.invasive
def test_park_tool(motion, tool_changer):
    motion.move_to({"Z": _PARK_Z})
    tool_changer.pickup_tool(0)
    ok = tool_changer.park_tool()

    assert ok is True
    assert tool_changer.get_active_tool_index() == -1

    tool = tool_changer.get_tool(0)
    assert tool.is_active_tool is False


@pytest.mark.invasive
def test_exchange_tools(motion, tool_changer):
    motion.move_to({"Z": _PARK_Z})
    assert tool_changer.pickup_tool(0) is True
    assert tool_changer.get_active_tool_index() == 0

    assert tool_changer.pickup_tool(1) is True
    assert tool_changer.get_active_tool_index() == 1

    tool0 = tool_changer.get_tool(0)
    tool1 = tool_changer.get_tool(1)

    assert tool0.is_active_tool is False
    assert tool1.is_active_tool is True


# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


@pytest.mark.invasive
def test_pickup_empty_slot(motion, tool_changer):
    motion.move_to({"Z": _PARK_Z})
    with pytest.raises(ToolSlotError):
        tool_changer.pickup_tool(3)


@pytest.mark.invasive
def test_pickup_tool_without_offset(motion, tool_changer):
    motion.move_to({"Z": _PARK_Z})
    with pytest.raises(ToolStateError):
        tool_changer.pickup_tool(2)
