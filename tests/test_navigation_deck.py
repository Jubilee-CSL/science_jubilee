import os

import pytest

from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.hal.transport.mock import MockTransport
from science_jubilee.decks.Deck import Deck
from science_jubilee.navigation import DeckNavigator


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
    plate = deck.load_labware(labware_def, slot=0)

    nav = DeckNavigator(driver=driver, deck=deck, labware_by_slot={0: plate})
    return nav, deck, plate




@pytest.mark.invasive
def test_navigation_with_motion_fixture_moves_control_point(motion):
    """Navigation should work with the shared MotionDriver fixture (mock or hardware).

    This test is transport-agnostic: when run with --jubilee-env mock it uses
    the digital twin; with --jubilee-env hardware it will move the real
    machine, so keep it under the 'invasive' marker.
    """

    driver = motion
    nav, deck, plate = _make_navigator_for_driver(driver)

    first_well = next(nav.iter_wells(plate, order="rows"))
    offset = 2.0
    loc = first_well.bottom(offset)
    x_exp, y_exp, z_exp = loc.point

    nav.move_to_well(
        first_well,
        z_from_bottom=offset,
        travel_margin=10.0,
        speed_xy=4000.0,
        speed_z=3000.0,
    )

    # Read back positions from the underlying transport via MotionDriver
    pos = driver.transport.get_positions() or {}
    assert pos.get("X") == pytest.approx(float(x_exp), rel=1e-3)
    assert pos.get("Y") == pytest.approx(float(y_exp), rel=1e-3)
    assert pos.get("Z") == pytest.approx(float(z_exp), rel=1e-3)
