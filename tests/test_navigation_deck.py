import os

import pytest

from science_jubilee.hal.motion_driver import MotionDriver
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

    pos = driver.get_positions()
    assert pos.get("X") == pytest.approx(float(x_exp), rel=1e-3)
    assert pos.get("Y") == pytest.approx(float(y_exp), rel=1e-3)
    assert pos.get("Z") == pytest.approx(float(z_exp), rel=1e-3)


@pytest.mark.invasive
def test_navigation_moves_to_all_wells(motion):
    """Iterate through all wells in the labware and move to each one (mock or hardware).

    Uses the shared MotionDriver fixture, so it runs against:
    - the digital twin when --jubilee-env mock
    - the real machine when --jubilee-env hardware
    """

    driver = motion
    nav, deck, plate = _make_navigator_for_driver(driver)

    # Iterate all wells row-wise, recording the expected position of the last one
    last_loc = None
    offset = 2.0
    count = 0
    for well in nav.iter_wells(plate, order="rows"):
        last_loc = well.bottom(offset)
        nav.move_to_well(
            well,
            z_from_bottom=offset,
            travel_margin=10.0,
            speed_xy=4000.0,
            speed_z=3000.0,
        )
        count += 1

    assert count == len(plate.wells)
    assert last_loc is not None
    x_exp, y_exp, z_exp = last_loc.point

    pos = driver.get_positions()
    assert pos.get("X") == pytest.approx(float(x_exp), rel=1e-3)
    assert pos.get("Y") == pytest.approx(float(y_exp), rel=1e-3)
    assert pos.get("Z") == pytest.approx(float(z_exp), rel=1e-3)
