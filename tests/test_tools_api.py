import logging
import pytest


logger = logging.getLogger(__name__)


@pytest.mark.secondary
def test_list_tools_and_active_index(transport):
    tools = transport.get_tools()
    assert isinstance(tools, dict)
    logger.info("Initial tools: %s", tools)

    active = transport.get_active_tool_index()
    assert isinstance(active, int)
    assert active in (-1, *tools.keys())

    transport.select_tool(0)
    assert transport.get_active_tool_index() == 0
    transport.select_tool(1)
    assert transport.get_active_tool_index() == 1

    tools2 = transport.get_tools()
    assert isinstance(tools2, dict)
    assert 0 in tools2 and 1 in tools2


@pytest.mark.secondary
def test_pickup_and_park_tool(transport):
    ok = transport.select_tool(0)
    assert ok is True
    assert transport.get_active_tool_index() == 0

    ok2 = transport.park_tool()
    assert ok2 is True
    assert transport.get_active_tool_index() == -1


@pytest.mark.secondary
def test_exchange_tools(transport):
    assert transport.select_tool(0) is True
    assert transport.get_active_tool_index() == 0
    assert transport.select_tool(1) is True
    assert transport.get_active_tool_index() == 1


@pytest.mark.secondary
def test_set_and_get_tool_offsets(transport):
    idx = 2
    assert transport.select_tool(idx) is True
    assert transport.set_tool_offset(idx, x=1.25, y=-2.5, z=12.34) is True
    offsets = transport.get_tool_offsets()
    assert isinstance(offsets, dict)
    assert idx in offsets
    ox, oy, oz = offsets[idx]
    assert abs(ox - 1.25) < 1e-6
    assert abs(oy - (-2.5)) < 1e-6
    assert abs(oz - 12.34) < 1e-6
