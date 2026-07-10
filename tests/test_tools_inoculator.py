import logging
import os

import pytest

from science_jubilee.tools.Tool import ToolStateError
from science_jubilee.tools.unique_tools.Inoculator import Inoculator

logger = logging.getLogger(__name__)


def make_inoculator(tool_changer):
    tool = tool_changer.get_tool(0)
    inoculator = Inoculator(index=tool.index, name=tool.name)
    tool_changer.tools[0] = inoculator


# ------------------------------------------------------------------
# Transfer safety
# ------------------------------------------------------------------
@pytest.mark.secondary
def test_transfer_requires_active_tool(tool_changer, navigator):
    """
    Transfer must fail if tool
    is not active.
    """
    make_inoculator(tool_changer)
    source = navigator.get_well("0","A1")
    destination = [navigator.get_well("0","A2")]

    inoculator = tool_changer.get_tool(0)

    with pytest.raises(ToolStateError):
        inoculator.transfer(navigator, source, destination)


# ------------------------------------------------------------------
# Basic transfer
# ------------------------------------------------------------------


@pytest.mark.invasive
def test_transfer(tool_changer, navigator):
    """
    Verify standard transfer.
    """
    make_inoculator(tool_changer)
    source = navigator.get_well("0","A1")
    destination = navigator.get_wells_in_slot(0)
    inoculator = tool_changer.get_tool(0)

    tool_changer.pickup_tool(0)

    inoculator.transfer(navigator, source, destination, randomize_pickup=False)
    tool_changer.park_tool()

    assert tool_changer.get_active_tool_index() == -1


# ------------------------------------------------------------------
# Randomized transfer
# ------------------------------------------------------------------


@pytest.mark.invasive
def test_transfer_randomized_pickup(tool_changer, navigator):
    """
    Verify randomized pickup transfer.
    """
    make_inoculator(tool_changer)
    source = navigator.get_well("0","A1")
    destination = [navigator.get_well("0","A2")]
    inoculator = tool_changer.get_tool(0)

    tool_changer.pickup_tool(0)

    inoculator.transfer(navigator, source, destination, randomize_pickup=True)
    tool_changer.park_tool()

# ------------------------------------------------------------------
# Runtime state
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_manual_activate_deactivate(tool_changer):
    """
    Verify manual activation state.
    """

    inoculator = tool_changer.get_tool(0)

    assert inoculator.is_active_tool is False

    inoculator.activate()
    assert inoculator.is_active_tool is True

    inoculator.deactivate()
    assert inoculator.is_active_tool is False
