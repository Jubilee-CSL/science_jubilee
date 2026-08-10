import time
from pathlib import Path

import numpy as np
from sacred import Ingredient

acquisition = Ingredient("acquisition")


@acquisition.config
def acquisition_config():
    mode = "simple"  # "simple" | "illuminated"
    nb_leds = 8  # number of LEDs used for illuminated mode
    debug = False  # save each individual LED image for inspection
    led_r = 50  # LED red channel   [0-255]
    led_g = 0  # LED green channel [0-255]
    led_b = 0  # LED blue channel  [0-255]


def _capture_multi_lighting(cam, light, nb_leds: int, r: int, g: int, b: int) -> list:
    light.all_pixel_off()
    images = []
    for i in range(nb_leds):
        light.pixel_on(i, r, g, b)
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
def acquire(
    cam, light, save_dir: Path, name: str, mode, nb_leds, debug, led_r, led_g, led_b
) -> str:
    """Capture one image (simple or illuminated) and save it. Returns the saved file path."""
    if mode == "illuminated":
        if light is None:
            raise ValueError(
                "mode=illuminated requires a light — set JUBILEE_NEOPIXEL_ADDRESS or pass light="
            )
        images = _capture_multi_lighting(cam, light, nb_leds, r=led_r, g=led_g, b=led_b)
        if debug:
            for i, img in enumerate(images):
                cam.save_image(
                    img=img, save_dir=save_dir, save_name=f"{name}_led{i:02d}"
                )
        img = _pixel_minimum(images)
    else:
        img = cam.get_image()

    cam.save_image(img=img, save_dir=save_dir, save_name=name)
    return str(save_dir / f"{name}.jpg")
