import logging

import pytest

from science_jubilee.tools.light.neopixel_mock import NeopixelMock

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Secondary: state tracking (mock only, no network)
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_pixel_on_sets_state(light):
    from science_jubilee.tools.light.neopixel_mock import NeopixelMock

    if not isinstance(light, NeopixelMock):
        pytest.skip("state-inspection test is mock-only")
    light.pixel_on(0, 255, 128, 0)
    assert light.state[0] == (255, 128, 0)


@pytest.mark.secondary
def test_pixel_off_clears_state(light):
    if not isinstance(light, NeopixelMock):
        pytest.skip("state-inspection test is mock-only")
    light.pixel_on(1, 100, 100, 100)
    light.pixel_off(1)
    assert light.state[1] == (0, 0, 0)


@pytest.mark.secondary
def test_all_pixel_on_sets_all(light):
    if not isinstance(light, NeopixelMock):
        pytest.skip("state-inspection test is mock-only")
    light.all_pixel_on(255, 255, 255)
    assert all(light.state[i] == (255, 255, 255) for i in range(8))


@pytest.mark.secondary
def test_all_pixel_off_clears_all(light):
    if not isinstance(light, NeopixelMock):
        pytest.skip("state-inspection test is mock-only")
    light.all_pixel_on(200, 200, 200)
    light.all_pixel_off()
    assert light.state == {}


# ------------------------------------------------------------------
# Invasive: full sequence (runs on both mock and hardware)
# ------------------------------------------------------------------


@pytest.mark.secondary
def test_light_sequence(light):
    """Cycle through 8 LEDs on and off — verifiable on hardware, logged on mock."""
    light.all_pixel_off()
    for i in range(8):
        light.pixel_on(i, 255, 255, 50)
        logger.info("LED %d on", i)
        light.pixel_off(i)
    light.all_pixel_off()
    logger.info("Sequence complete")
