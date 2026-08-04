import logging

from science_jubilee.tools.light.base import BaseLight

logger = logging.getLogger(__name__)


class NeopixelMock(BaseLight):
    """In-process light that records state without any network calls."""

    def __init__(self):
        self.state: dict[int, tuple[int, int, int]] = {}

    def pixel_on(self, led_index, r, g, b):
        self.state[led_index] = (r, g, b)
        logger.debug("NeopixelMock: pixel %d -> (%d, %d, %d)", led_index, r, g, b)

    def pixel_off(self, led_index):
        self.state[led_index] = (0, 0, 0)
        logger.debug("NeopixelMock: pixel %d off", led_index)

    def all_pixel_on(self, r, g, b):
        for i in range(8):
            self.state[i] = (r, g, b)
        logger.debug("NeopixelMock: all pixels -> (%d, %d, %d)", r, g, b)

    def all_pixel_off(self):
        self.state.clear()
        logger.debug("NeopixelMock: all pixels off")
