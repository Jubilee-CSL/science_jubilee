import logging
import pytest


logger = logging.getLogger(__name__)


@pytest.mark.secondary
def test_list_tools_and_active_index(motion):
    """List tools, pick up tools to populate mock, and verify active tool index.

    In simulation, MockTransport starts empty; selecting tools creates entries.
    On hardware, tools[] comes from the Duet config.
    """
    driver = motion

    tools = driver.list_tools()
    assert isinstance(tools, dict)
    logger.info("Initial tools: %s", tools)

    # Active tool should be -1 initially
    active = driver.get_active_tool_index()
    assert isinstance(active, int)
    assert active in (-1, *tools.keys())

    # Select two tools to populate mock or switch hardware
    driver.pickup_tool(0)
    assert driver.get_active_tool_index() == 0
    driver.pickup_tool(1)
    assert driver.get_active_tool_index() == 1

    tools2 = driver.list_tools()
    assert isinstance(tools2, dict)
    # In mock, both 0 and 1 should exist now
    assert 0 in tools2 and 1 in tools2


@pytest.mark.secondary
def test_pickup_and_park_tool(motion):
    """Select a tool and then park it; verify the active tool index changes accordingly."""
    driver = motion
    ok = driver.pickup_tool(0)
    assert ok is True
    assert driver.get_active_tool_index() == 0

    ok2 = driver.park_tool()
    assert ok2 is True
    assert driver.get_active_tool_index() == -1


@pytest.mark.secondary
def test_exchange_tools(motion):
    """Select tool 0, then tool 1, ensuring the active tool switches."""
    driver = motion
    assert driver.pickup_tool(0) is True
    assert driver.get_active_tool_index() == 0
    assert driver.pickup_tool(1) is True
    assert driver.get_active_tool_index() == 1


@pytest.mark.secondary
def test_set_and_get_tool_offsets(motion):
    """Set offsets for a tool and verify they are reported by transport."""
    driver = motion
    idx = 2
    assert driver.pickup_tool(idx) is True
    # Set offsets
    assert driver.set_tool_offset(idx, x=1.25, y=-2.5, z=12.34) is True
    offsets = driver.get_tool_offsets()
    assert isinstance(offsets, dict)
    assert idx in offsets
    ox, oy, oz = offsets[idx]
    assert abs(ox - 1.25) < 1e-6
    assert abs(oy - (-2.5)) < 1e-6
    assert abs(oz - 12.34) < 1e-6
