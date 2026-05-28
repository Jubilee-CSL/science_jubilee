import logging
import os

import pytest

from science_jubilee.decks.Deck import Deck
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.navigation.deck_navigation import (
    DeckNavigator,
)

from science_jubilee.tools.Tool import (
    ToolStateError,
)

from science_jubilee.tools.unique_tools.Inoculator import (
    Inoculator,
)

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Environment helpers
# ------------------------------------------------------------------
def _get_defs_from_env() -> tuple[str, str]:
    """
    Return:
        deck_definition,
        labware_definition
    """

    deck_def = os.getenv("JUBILEE_DECK_DEF","lab_automation_deck_AFL_bolton.json",)
    labware_def = os.getenv("JUBILEE_LABWARE_DEF","corning_96_wellplate_360ul_flat.json",)

    return (deck_def,labware_def)


def _make_navigator_for_driver(driver: MotionDriver):
    """
    Construct test navigation environment.
    """
    deck_def, labware_def = (_get_defs_from_env())
    deck = Deck(deck_def)

    deck.load_labware(labware_def,slot_id=0)
    nav = DeckNavigator(driver=driver,deck=deck,)

    return nav


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def make_inoculator(nav: DeckNavigator) -> Inoculator:
    """
    Create configured inoculator.
    """
    inoculator = Inoculator(nav=nav,index=0,name="inoculator")
    inoculator.set_offset(0,7,18)
    return inoculator


# ------------------------------------------------------------------
# Tool initialization
# ------------------------------------------------------------------

@pytest.mark.secondary
def test_inoculator_creation(motion):
    """
    Verify inoculator initialization.
    """

    nav=_make_navigator_for_driver(motion)
    inoculator = make_inoculator(nav)

    assert inoculator.name == "inoculator"
    assert inoculator.index == 0
    assert (inoculator.tool_offset_is_set is True)
    assert (inoculator.get_offset_tuple() == (0.0, 7.0, 18.0))


# ------------------------------------------------------------------
# Activation lifecycle
# ------------------------------------------------------------------

@pytest.mark.secondary
def test_inoculator_activation(motion,tool_changer,):
    """
    Verify activation/deactivation lifecycle.
    """

    nav = _make_navigator_for_driver(motion)
    inoculator = make_inoculator(nav)

    tool_changer.load_tool(inoculator)
    assert (inoculator.is_active_tool is False)

    tool_changer.pickup_tool(0)
    assert (inoculator.is_active_tool is True)

    tool_changer.park_tool()

    assert (inoculator.is_active_tool is False)


# ------------------------------------------------------------------
# Transfer safety
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_transfer_requires_active_tool(motion):
    """
    Transfer must fail if tool
    is not active.
    """

    nav = _make_navigator_for_driver(motion)
    inoculator = make_inoculator(nav)

    source = nav.deck.get_well("0","A1")
    destination = nav.deck.get_well("0","A2")

    with pytest.raises(ToolStateError):
        inoculator.transfer(source,destination,)

# ------------------------------------------------------------------
# Basic transfer
# ------------------------------------------------------------------

@pytest.mark.invasive
def test_transfer(motion,tool_changer):
    """
    Verify standard transfer.
    """

    nav =_make_navigator_for_driver(motion)
    source = nav.deck.get_well("0","A1")
    destination = nav.deck.get_well("0","A2")
    inoculator = make_inoculator(nav)

    tool_changer.load_tool(inoculator)
    tool_changer.pickup_tool(0)

    inoculator.transfer(source,destination,randomize_pickup=False)
    tool_changer.unload_tool(0)

    assert (tool_changer.get_active_tool_index()== -1)


# ------------------------------------------------------------------
# Randomized transfer
# ------------------------------------------------------------------

@pytest.mark.invasive
def test_transfer_randomized_pickup(motion,tool_changer,):
    """
    Verify randomized pickup transfer.
    """

    nav = _make_navigator_for_driver(motion)
    source = nav.deck.get_well("0","A1")
    destination = nav.deck.get_well("0","A2")
    inoculator = make_inoculator(nav)

    tool_changer.load_tool(inoculator)
    tool_changer.pickup_tool(0)

    inoculator.transfer(source,destination,randomize_pickup=True)
    tool_changer.unload_tool(0)


# ------------------------------------------------------------------
# Transfer to all wells
# ------------------------------------------------------------------


@pytest.mark.invasive
def test_transfer_to_all_wells(motion,tool_changer):
    """
    Verify broadcast transfer
    over full destination plate.
    """

    nav = _make_navigator_for_driver(motion)
    inoculator = make_inoculator(nav)

    tool_changer.load_tool(inoculator)
    tool_changer.pickup_tool(0)

    inoculator.transfert_to_all_well(
        slot_source="0",
        slot_destination="0",
        randomize_pickup=False,
    )

    tool_changer.unload_tool(0)


# ------------------------------------------------------------------
# Offset handling
# ------------------------------------------------------------------

@pytest.mark.secondary
def test_offset_update(motion):
    """
    Verify offset mutation.
    """

    nav = _make_navigator_for_driver(motion)
    inoculator = make_inoculator(nav)
    inoculator.set_offset(1,2,3,)

    assert (inoculator.get_offset_tuple()== (1.0, 2.0, 3.0))


@pytest.mark.secondary
def test_offset_reset(motion,):
    """
    Verify offset reset.
    """

    nav =_make_navigator_for_driver(motion)
    inoculator = make_inoculator(nav)
    inoculator.reset_offset()

    assert (inoculator.tool_offset_is_set is False)
    assert (inoculator.get_offset_tuple()== (None, None, None))


# ------------------------------------------------------------------
# Runtime state
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_manual_activate_deactivate(motion):
    """
    Verify manual activation state.
    """

    nav =_make_navigator_for_driver(motion)
    inoculator = make_inoculator(nav)

    assert (inoculator.is_active_tool is False)

    inoculator.activate()
    assert (inoculator.is_active_tool is True)
    
    inoculator.deactivate()
    assert (inoculator.is_active_tool is False)
