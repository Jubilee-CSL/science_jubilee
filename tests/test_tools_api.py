import logging
import pytest

from science_jubilee.tools.Tool import Tool

logger = logging.getLogger(__name__)

def loading_tools(tool_changer):
    inoculateur = Tool(0,"inoculateur",5 ,5, 5)
    pipette = Tool(1,"pipette",10, 10, 20)

    tool_changer.load_tool(inoculateur)
    tool_changer.load_tool(pipette)
    

def unloading_tools(tool_changer):
    tool_changer.unload_tool(0)
    tool_changer.unload_tool(1)

@pytest.mark.secondary
def test_loading_unloading_tools(tool_changer):
    initial_tool = tool_changer.state_tools()
    assert isinstance(initial_tool, dict)
    logger.info("tools state: %s", initial_tool)

    loading_tools(tool_changer)
    loaded_tools = tool_changer.get_tools()
    logger.info("Loaded tools: %s", loaded_tools)

    tools = tool_changer.state_tools()
    logger.info("tools state: %s", tools)

    unloading_tools(tool_changer)

    final_tools = tool_changer.state_tools()
    logger.info("tools state: %s", final_tools)

    assert initial_tool == final_tools

@pytest.mark.secondary
def test_list_tools_and_active_index(tool_changer):
    tools = tool_changer.state_tools()
    logger.info("tools state: %s", tools)

    active = tool_changer.get_active_tool_index()
    assert isinstance(active, int)
    assert active in (-1, *tools.keys())

    loading_tools(tool_changer)

    tools = tool_changer.state_tools()
    logger.info("Loaded Tools: %s", tools)


    tool_changer.pickup_tool(0)
    assert tool_changer.get_active_tool_index() == 0
    tool_changer.pickup_tool(1)
    assert tool_changer.get_active_tool_index() == 1

    unloading_tools(tool_changer)

@pytest.mark.secondary
def test_pickup_and_park_tool(tool_changer):

    loading_tools(tool_changer)
    ok = tool_changer.pickup_tool(0)
    assert ok is True
    assert tool_changer.get_active_tool_index() == 0

    ok2 = tool_changer.park_tool()
    assert ok2 is True
    assert tool_changer.get_active_tool_index() == -1

    unloading_tools(tool_changer)


@pytest.mark.secondary
def test_exchange_tools(tool_changer):
    loading_tools(tool_changer)
    assert tool_changer.pickup_tool(0) is True
    assert tool_changer.get_active_tool_index() == 0
    assert tool_changer.pickup_tool(1) is True
    assert tool_changer.get_active_tool_index() == 1
    unloading_tools(tool_changer)


@pytest.mark.secondary
def test_set_and_get_tool_offsets(tool_changer):
    inoculateur = Tool(0,"inoculateur",5 ,5, 5)
    tool_changer.load_tool(inoculateur)
    
    idx = 0
    assert tool_changer.pickup_tool(idx) is True
    offsets = tool_changer.state_tool_offsets()
    logger.info("offsets Tools: %s", offsets)

    assert isinstance(offsets, dict)
    assert idx in offsets
    ox, oy, oz = offsets[idx]
    assert abs(ox - 5) < 1e-6
    assert abs(oy - 5) < 1e-6
    assert abs(oz - 5) < 1e-6

    tool_changer.unload_tool(0)

