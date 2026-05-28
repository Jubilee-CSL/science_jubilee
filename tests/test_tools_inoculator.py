import logging
import pytest
import os

from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.navigation import DeckNavigator
from science_jubilee.tools.unique_tools.Inoculator import Inoculator
from science_jubilee.decks.Deck import Deck

logger = logging.getLogger(__name__)

def _get_defs_from_env() -> tuple[str, str]:
    """Return (deck_definition, labware_definition) from environment.

    Defaults are set in tests/conftest.py but can be overridden via
    JUBILEE_DECK_DEF and JUBILEE_LABWARE_DEF.
    """

    deck_def = os.getenv("JUBILEE_DECK_DEF", "lab_automation_deck_AFL_bolton.json")
    labware_def = os.getenv(
        "JUBILEE_LABWARE_DEF", "corning_96_wellplate_360ul_flat.json"
    )
    return deck_def, labware_def

def _make_navigator_for_driver(driver: MotionDriver):
    """Construct a DeckNavigator for a given MotionDriver (mock or hardware)."""

    deck_def, labware_def = _get_defs_from_env()

    # Load a deck and labware into slot 0.
    deck = Deck(deck_def)
    plate = deck.load_labware(labware_def, slot_id=0)

    nav = DeckNavigator(driver=driver, deck=deck )
    return nav, deck, plate

@pytest.mark.invasive
def test_transfer(motion, tool_changer):
    driver = motion 
    nav, deck, plate = _make_navigator_for_driver(driver)

    well_source = nav.deck.get_well("0","A1")
    well_destination = nav.deck.get_well("0","A2")

    inoculateur = Inoculator(nav, 0, "inoculateur")
    inoculateur.set_offset(0, 7, 18)
    tool_changer.load_tool(inoculateur)
    tool_changer.pickup_tool(0)

    #a terme il faudrait charger l'outil automatiquement comme le deck 
    #et récupérer l'outil inoculateur dans la liste de tools de toolchanger 
    #sans l'initier à la main
    inoculateur.transfer(well_source,well_destination,randomize_pickup = False)

    tool_changer.unload_tool(0)

@pytest.mark.invasive
def test_transfer_randomize(motion, tool_changer):
    driver = motion 
    nav, deck, plate = _make_navigator_for_driver(driver)

    inoculateur = Inoculator(nav,0,"inoculateur", 0, 7, 18)
    tool_changer.load_tool(inoculateur)
    tool_changer.pickup_tool(0)

    slot = nav.deck.get_slot(0)

    inoculateur.transfert(slot,slot,randomize_pickup = False)

    tool_changer.unload_tool(0)



