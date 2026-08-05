import logging
import time
from pathlib import Path

import numpy as np
from sacred import Ingredient

logger = logging.getLogger(__name__)

acquisition = Ingredient("acquisition")


@acquisition.config
def acquisition_config():
    mode    = "simple"  # "simple" | "illuminated"
    nb_leds = 8         # number of LEDs used for illuminated mode


def _capture_multi_lighting(cam, light, nb_leds: int) -> list:
    light.all_pixel_off()
    images = []
    for i in range(nb_leds):
        light.pixel_on(i, 255, 255, 50)
        time.sleep(3)
        images.append(cam.get_image())
        light.pixel_off(i)
        time.sleep(0.2)
    return images


def _pixel_minimum(images: list) -> np.ndarray:
    result = images[0].copy()
    for img in images[1:]:
        result = np.minimum(result, img)
    return result


@acquisition.capture
def acquire(cam, light, save_dir: Path, name: str, mode, nb_leds) -> str:
    """Capture one image (simple or illuminated) and save it. Returns the saved file path."""
    if mode == "illuminated":
        if light is None:
            logger.warning("mode=illuminated but no light available, falling back to simple")
            img = cam.get_image()
        else:
            images = _capture_multi_lighting(cam, light, nb_leds)
            img = _pixel_minimum(images)
    else:
        img = cam.get_image()

    cam.save_image(img=img, save_dir=save_dir, save_name=name)
    return str(save_dir / f"{name}.jpg")
