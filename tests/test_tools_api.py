import logging
import pytest

from science_jubilee.tools.Tool import Tool

from science_jubilee.hal.tool_changer import (
    ToolSlotError,
    ToolSyncError,
    ToolStateError
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def make_tool(nav,index: int,name: str,
    x: float | None = None,
    y: float | None = None,
    z: float | None = None,
) -> Tool:
    """
    Helper factory for tests.
    """
    tool = Tool(nav=nav,index=index,name=name,)

    if (x is not None and y is not None and z is not None):
        tool.set_offset(x, y, z)

    return tool


def load_default_tools(tool_changer,nav):
    """
    Load two default tools.
    """

    inoculateur = make_tool(nav,0,"inoculateur",5,5,5,)
    pipette = make_tool(nav,1,"pipette",10,10,20,)

    tool_changer.load_tool(inoculateur)
    tool_changer.load_tool(pipette)


def unload_default_tools(tool_changer):

    tool_changer.unload_tool(0)
    tool_changer.unload_tool(1)


# ------------------------------------------------------------------
# Tool lifecycle
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_loading_unloading_tools(tool_changer,navigator):
    """
    Verify tool loading/unloading lifecycle.
    """

    initial_state = (tool_changer.state_tools())
    logger.info("Initial tools: %s",initial_state,)

    load_default_tools(tool_changer,navigator)

    tools = (tool_changer.get_tools())

    assert tools[0] is not None
    assert tools[1] is not None

    logger.info("Loaded tools: %s",tools,)

    unload_default_tools(tool_changer)

    final_state = (tool_changer.state_tools())

    logger.info("Final tools: %s",final_state,)

    assert initial_state == final_state


# ------------------------------------------------------------------
# Tool activation
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_pickup_tool(tool_changer,navigator,):
    """
    Verify tool activation.
    """
    load_default_tools(tool_changer,navigator,)
    ok = tool_changer.pickup_tool(0)

    assert ok is True
    assert (tool_changer.get_active_tool_index()== 0)

    tool = tool_changer.get_tools()[0]
    assert tool.is_active_tool is True

    unload_default_tools(tool_changer)


@pytest.mark.secondary
def test_park_tool(tool_changer,navigator):
    """
    Verify tool parking.
    """

    load_default_tools(tool_changer,navigator)

    tool_changer.pickup_tool(0)
    ok = tool_changer.park_tool()

    assert ok is True
    assert (tool_changer.get_active_tool_index()== -1)

    tool = tool_changer.get_tools()[0]
    assert tool.is_active_tool is False

    unload_default_tools(tool_changer)



@pytest.mark.secondary
def test_exchange_tools(tool_changer,navigator):
    """
    Verify switching active tools.
    """

    load_default_tools(tool_changer,navigator,)

    assert (tool_changer.pickup_tool(0) is True)
    assert (tool_changer.get_active_tool_index()== 0)

    assert (tool_changer.pickup_tool(1)is True)
    assert (tool_changer.get_active_tool_index()== 1)

    tools = (tool_changer.get_tools())

    assert (tools[0].is_active_tool is False)
    assert (tools[1].is_active_tool is True)

    unload_default_tools(tool_changer)



# ------------------------------------------------------------------
# Offsets
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_tool_offsets(tool_changer,navigator,):
    """
    Verify offset propagation.
    """

    tool = make_tool(navigator,0,"pipette",5,5,5)
    tool_changer.load_tool(tool)

    offsets = (tool_changer.state_tool_offsets())

    logger.info("Offsets: %s",offsets,)

    assert 0 in offsets

    ox, oy, oz = offsets[0]

    assert ox == 5
    assert oy == 5
    assert oz == 5

    tool_changer.unload_tool(0)


@pytest.mark.secondary
def test_set_tool_offset(tool_changer,navigator,):
    """
    Verify runtime offset update.
    """

    tool = make_tool(navigator,0,"pipette",)
    tool_changer.load_tool(tool)

    ok = tool_changer.set_tool_offset(0,x=12.5,y=7.0,z=3.5,)

    assert ok is True

    offsets = (tool_changer.state_tool_offsets())
    ox, oy, oz = offsets[0]

    assert ox == 12.5
    assert oy == 7.0
    assert oz == 3.5

    loaded_tool = (tool_changer.get_tools()[0])

    assert (loaded_tool.get_offset_tuple()== (12.5, 7.0, 3.5))

    tool_changer.unload_tool(0)



# ------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_loading_same_slot_twice(tool_changer,navigator,):
    """
    Loading twice into same slot
    must fail.
    """

    tool_a = make_tool(navigator,0,"tool_a",)
    tool_b = make_tool(navigator,0,"tool_b",)

    tool_changer.load_tool(tool_a)

    with pytest.raises(ToolSlotError):
        tool_changer.load_tool(tool_b)
    
    tool_changer.unload_tool(0)



@pytest.mark.secondary
def test_unload_empty_slot(tool_changer,):
    """
    Unloading empty slot
    must fail.
    """

    with pytest.raises(ToolSlotError):
        tool_changer.unload_tool(0)


@pytest.mark.secondary
def test_pickup_empty_slot(tool_changer,):
    """
    Selecting empty slot
    must fail.
    """

    with pytest.raises(ToolSlotError):
        tool_changer.pickup_tool(0)


@pytest.mark.secondary
def test_pickup_same_tool_twice(tool_changer,navigator,):
    """
    Picking active tool twice
    must fail.
    """

    load_default_tools(tool_changer,navigator)
    tool_changer.pickup_tool(0)

    with pytest.raises(ToolStateError):
        tool_changer.pickup_tool(0)

    unload_default_tools(tool_changer)


@pytest.mark.secondary
def test_pickup_tool_without_offset(tool_changer,navigator,):
    """
    Tool without offset
    must not be usable.
    """

    tool = make_tool(navigator,0,"invalid_tool",)
    tool_changer.load_tool(tool)

    with pytest.raises(ToolStateError):
        tool_changer.pickup_tool(0)
    
    tool_changer.unload_tool(0)


# ------------------------------------------------------------------
# Synchronization
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_sync_detection(tool_changer,navigator):
    """
    Verify desynchronization detection.
    """

    load_default_tools(tool_changer,navigator,)
    tool_changer.pickup_tool(0)

    tool = (tool_changer.get_tools()[0])

    # Simulate corruption
    tool.is_active_tool = False

    with pytest.raises(ToolSyncError):
        tool_changer.sync()

    unload_default_tools(tool_changer)



