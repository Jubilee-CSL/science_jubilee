import os
import pytest

from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.decks.Deck import Deck
from science_jubilee.navigation import DeckNavigator


@pytest.mark.invasive
def test_navigation_with_motion_fixture_moves_control_point(navigator):
    """Navigation should work with the shared MotionDriver fixture (mock or hardware).

    This test is transport-agnostic: when run with --jubilee-env mock it uses
    the digital twin; with --jubilee-env hardware it will move the real
    machine, so keep it under the 'invasive' marker.
    """

    well = navigator.get_well("0","A1")
    offset = 2.0
    loc = well.get_bottom_location(z_offset=offset)
    x_exp, y_exp, z_exp = loc.point

    navigator.move_to_target(
        well,
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
    nav = _make_navigator_for_driver(driver)

    # Iterate all wells row-wise, recording the expected position of the last one
    last_loc = None
    offset = 2.0
    count = 0
    labware = nav.get_labware_in_slot(0)
    for well in labware:
        last_loc = well.get_bottom_location(z_offset=offset)
        nav.move_to_target(
            well,
            z_from_bottom=offset,
            travel_margin=10.0,
            speed_xy=4000.0,
            speed_z=3000.0,
        )
        count += 1

    assert count == len(labware.wells)
    assert last_loc is not None
    x_exp, y_exp, z_exp = last_loc.point

    pos = driver.get_positions()
    assert pos.get("X") == pytest.approx(float(x_exp), rel=1e-3)
    assert pos.get("Y") == pytest.approx(float(y_exp), rel=1e-3)
    assert pos.get("Z") == pytest.approx(float(z_exp), rel=1e-3)
