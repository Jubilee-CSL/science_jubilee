import math
from unittest.mock import Mock

import pytest

from science_jubilee.labware.Labware import (
    Location,
    Point,
    Well,
)
from science_jubilee.tools.unique_tools.Inoculator import (
    Inoculator,
)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def source_well():
    return Well(
        name="A1",
        depth=10,
        totalLiquidVolume=100,
        shape="circular",
        diameter=20,
        x=100,
        y=100,
        z=0,
    )


@pytest.fixture
def destination_well():
    return Well(
        name="B1",
        depth=10,
        totalLiquidVolume=100,
        shape="circular",
        diameter=20,
        x=200,
        y=200,
        z=0,
    )


@pytest.fixture
def inoculator():
    tool = Inoculator(
        index=0,
        name="Inoculator",
    )

    tool.activate()

    return tool


@pytest.fixture
def mock_navigation(monkeypatch):

    navigation = Mock()

    monkeypatch.setattr(
        "science_jubilee.tools.Inoculator.navigation",
        navigation,
    )

    return navigation


# ======================================================================
# Tool state
# ======================================================================

@pytest.mark.secondary
def test_transfer_requires_active_tool(
    source_well,
    destination_well,
):
    tool = Inoculator(
        index=0,
        name="Inoculator",
    )

    with pytest.raises(Exception):

        tool.transfer(
            source_well,
            destination_well,
        )


# ======================================================================
# Navigation
# ======================================================================

@pytest.mark.secondary
def test_transfer_finishes_with_safe_z(
    inoculator,
    source_well,
    destination_well,
    mock_navigation,
):
    inoculator.transfer(
        source_well,
        destination_well,
    )

    mock_navigation.move_to_safe_z.assert_called_once()


# ======================================================================
# Random pickup geometry
# ======================================================================

@pytest.mark.secondary
def test_random_pickup_stays_inside_well(
    inoculator,
    source_well,
    destination_well,
    mock_navigation,
):
    captured_locations = []

    def capture_move(
        target,
        *args,
        **kwargs,
    ):
        if isinstance(target, Location):
            captured_locations.append(target)

    mock_navigation.move_to_target.side_effect = (
        capture_move
    )

    inoculator.transfer(
        source_well,
        destination_well,
        randomize_pickup=True,
    )

    pickup_location = captured_locations[0]

    dx = (
        pickup_location.point.x
        - source_well.x
    )

    dy = (
        pickup_location.point.y
        - source_well.y
    )

    distance = math.sqrt(
        dx**2 + dy**2
    )

    max_radius = (
        source_well.diameter / 2
    ) * 0.7

    assert distance <= max_radius


# ======================================================================
# Sweep safety
# ======================================================================

@pytest.mark.secondary
def test_sweep_stays_inside_well(
    inoculator,
    source_well,
    destination_well,
    mock_navigation,
):
    captured_locations = []

    def capture_move(
        target,
        *args,
        **kwargs,
    ):
        if isinstance(target, Location):
            captured_locations.append(target)

    mock_navigation.move_to_target.side_effect = (
        capture_move
    )

    inoculator.transfer(
        source_well,
        destination_well,
        sweep_x=1000,
        sweep_y=1000,
    )

    sweep_location = captured_locations[1]

    dx = (
        sweep_location.point.x
        - source_well.x
    )

    dy = (
        sweep_location.point.y
        - source_well.y
    )

    distance = math.sqrt(
        dx**2 + dy**2
    )

    max_radius = (
        source_well.diameter / 2
    ) * 0.85

    assert distance <= max_radius


# ======================================================================
# Destination movement
# ======================================================================

@pytest.mark.secondary
def test_transfer_moves_to_destination(
    inoculator,
    source_well,
    destination_well,
    mock_navigation,
):
    captured_locations = []

    def capture_move(
        target,
        *args,
        **kwargs,
    ):
        if isinstance(target, Location):
            captured_locations.append(target)

    mock_navigation.move_to_target.side_effect = (
        capture_move
    )

    inoculator.transfer(
        source_well,
        destination_well,
    )

    destination_location = captured_locations[-1]

    assert (
        destination_location.point.x
        >= destination_well.x
    )

    assert (
        destination_location.point.y
        >= destination_well.y
    )


# ======================================================================
# Multiple transfers
# ======================================================================

@pytest.mark.secondary
def test_transfer_to_all_wells(
    inoculator,
    source_well,
    mock_navigation,
    monkeypatch,
):
    destination_wells = [
        Well(
            name=f"A{i}",
            depth=10,
            totalLiquidVolume=100,
            shape="circular",
            diameter=20,
            x=i * 10,
            y=0,
            z=0,
        )
        for i in range(1, 5)
    ]

    fake_labware = destination_wells

    mock_navigation.get_well.return_value = (
        source_well
    )

    mock_navigation.get_labware_in_slot.return_value = (
        fake_labware
    )

    inoculator.transfer = Mock()

    inoculator.transfert_to_all_well(
        source="1",
        destination="2",
    )

    assert (
        inoculator.transfer.call_count
        == len(destination_wells)
    )