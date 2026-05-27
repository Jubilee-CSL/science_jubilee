import logging
import pytest

from science_jubilee.tools.Tool import Tool

logger = logging.getLogger(__name__)


@pytest.mark.secondary
def test_list_tools_and_active_index(tool_changer):
    tools = tool_changer.tools_state()
    assert isinstance(tools, dict)
    logger.info("tools state: %s", tools)

    active = tool_changer.get_active_tool_index()
    assert isinstance(active, int)
    assert active in (-1, *tools.keys())

    inoculateur = Tool(0,"inoculateur",False)
    pipette = Tool(1,"pipette",False)

    #tool_changer.load_tool(inoculateur.index,inoculateur.name)
    #tool_changer.load_tool(pipette.index,pipette.name)

    tools = tool_changer.tools_state()
    assert isinstance(tools, dict)
    logger.info("Initial tools: %s", tools)

    tool_changer.pickup_tool(0)
    assert tool_changer.get_active_tool_index() == 0
    tool_changer.pickup_tool(1)
    assert tool_changer.get_active_tool_index() == 1

    tools2 = tool_changer.get_tools()
    logger.info("Loaded tools: %s", tools2)
    assert isinstance(tools2, dict)
    assert 0 in tools2 and 1 in tools2


@pytest.mark.secondary
def test_pickup_and_park_tool(tool_changer):
    ok = tool_changer.pickup_tool(0)
    assert ok is True
    assert tool_changer.get_active_tool_index() == 0

    ok2 = tool_changer.park_tool()
    assert ok2 is True
    assert tool_changer.get_active_tool_index() == -1


@pytest.mark.secondary
def test_exchange_tools(tool_changer):
    assert tool_changer.pickup_tool(0) is True
    assert tool_changer.get_active_tool_index() == 0
    assert tool_changer.pickup_tool(1) is True
    assert tool_changer.get_active_tool_index() == 1


@pytest.mark.secondary
def test_set_and_get_tool_offsets(tool_changer):
    idx = 2
    assert tool_changer.pickup_tool(idx) is True
    assert tool_changer.set_tool_offset(idx, x=1.25, y=-2.5, z=12.34) is True
    offsets = tool_changer.state_tool_offsets()
    assert isinstance(offsets, dict)
    assert idx in offsets
    ox, oy, oz = offsets[idx]
    assert abs(ox - 1.25) < 1e-6
    assert abs(oy - (-2.5)) < 1e-6
    assert abs(oz - 12.34) < 1e-6
