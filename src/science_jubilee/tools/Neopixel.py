import logging
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class Neopixel:
    url: str

    def pixel_on(self, led_index, r, g, b):
        requests.get(f"{self.url}/pixel/{led_index}/{r}/{g}/{b}")

    def pixel_off(self, led_index):
        requests.get(f"{self.url}/pixel/{led_index}/0/0/0")

    def all_pixel_on(self, r, g, b):
        requests.get(f"{self.url}/led/{r}/{g}/{b}")

    def all_pixel_off(self):
        requests.get(f"{self.url}/off")
