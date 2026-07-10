import logging


from science_jubilee.hal.tool_changer import (
    ToolSlotError,
    ToolStateError
)
from science_jubilee.tools.Tool import Tool

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Tool activation
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_pickup_tool(tool_changer):
    """
    Verify tool activation.
    """
    ok = tool_changer.pickup_tool(0)

    assert ok is True
    assert tool_changer.get_active_tool_index() == 0

    tool = tool_changer.get_tool(0)
    assert tool.is_active_tool is True
    assert tool_changer.get_active_tool_index() == tool.index
    tool_changer.park_tool()


@pytest.mark.secondary
def test_park_tool(tool_changer):
    """
    Verify tool parking.
    """
    tool_changer.pickup_tool(0)
    ok = tool_changer.park_tool()

    assert ok is True
    assert tool_changer.get_active_tool_index() == -1

    tool = tool_changer.get_tool(0)
    assert tool.is_active_tool is False


@pytest.mark.secondary
def test_exchange_tools(tool_changer):
    """
    Verify switching active tools.
    """
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


@pytest.mark.secondary
def test_pickup_empty_slot(tool_changer):
    """
    Selecting empty slot
    must fail.
    """

    with pytest.raises(ToolSlotError):
        tool_changer.pickup_tool(3)


@pytest.mark.secondary
def test_pickup_tool_without_offset(tool_changer):
    """
    Tool without offset
    must not be usable.
    """
    with pytest.raises(ToolStateError):
        tool_changer.pickup_tool(2)
