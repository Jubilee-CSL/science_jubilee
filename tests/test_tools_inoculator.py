import logging
import os

import pytest

from science_jubilee.tools.Tool import ToolStateError


logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Transfer safety
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_transfer_requires_active_tool(tool_changer,navigator):
    """
    Transfer must fail if tool
    is not active.
    """

    source = navigator.deck.get_well("0","A1")
    destination = navigator.deck.get_well("0","A2")

    inoculator = tool_changer.get_tool(0)

    with pytest.raises(ToolStateError):
        inoculator.transfer(navigator,source,destination)

# ------------------------------------------------------------------
# Basic transfer
# ------------------------------------------------------------------

@pytest.mark.invasive
def test_transfer(tool_changer,navigator):
    """
    Verify standard transfer.
    """

    source = navigator.deck.get_well("0","A1")
    destination = navigator.deck.get_well("0","A2")
    inoculator = tool_changer.get_tool(0)

    tool_changer.pickup_tool(0)

    inoculator.transfer(navigator,source,destination,randomize_pickup=False)
    tool_changer.park_tool()

    assert (tool_changer.get_active_tool_index()== -1)

# ------------------------------------------------------------------
# Randomized transfer
# ------------------------------------------------------------------

@pytest.mark.invasive
def test_transfer_randomized_pickup(tool_changer,navigator):
    """
    Verify randomized pickup transfer.
    """
    source = navigator.deck.get_well("0","A1")
    destination = navigator.deck.get_well("0","A2")
    inoculator = tool_changer.get_tool(0)

    tool_changer.pickup_tool(0)

    inoculator.transfer(source,destination,randomize_pickup=True)
    tool_changer.park_tool()


# ------------------------------------------------------------------
# Transfer to all wells
# ------------------------------------------------------------------

@pytest.mark.invasive
def test_transfer_to_all_wells(tool_changer,navigator):
    """
    Verify broadcast transfer
    over full destination plate.
    """
    inoculator = tool_changer.get_tool(0)

    tool_changer.pickup_tool(0)

    inoculator.transfert_to_all_well(
        navigator,
        slot_source="0",
        slot_destination="0",
        randomize_pickup=False,
    )

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

    assert (inoculator.is_active_tool is False)

    inoculator.activate()
    assert (inoculator.is_active_tool is True)
    
    inoculator.deactivate()
    assert (inoculator.is_active_tool is False)
