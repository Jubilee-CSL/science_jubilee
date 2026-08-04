from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import cv2
import numpy as np

if TYPE_CHECKING:
    from science_jubilee.tools.Neopixel import Neopixel

logger = logging.getLogger(__name__)


class BaseCamera(ABC):
    """Abstract camera interface.

    Subclasses implement get_image(); all other methods are shared.
    """

    def __init__(self, motion, tool_changer) -> None:
        self.driver = motion
        self.tool_changer = tool_changer

        self.K = np.array(
            [
                [1223.5800404310712, 0, 1012.6265109062106],
                [0, 1234.9709223262516, 652.0441120068181],
                [0, 0, 1],
            ],
            dtype=np.float64,
        )
        self.dist = np.array(
            [
                0.003964559927730257,
                -0.07805139087827796,
                0.000522562108766698,
                -0.000680263815167156,
                0.26622436928189075,
            ]
        )
        self.R_machine_camera = np.eye(3, dtype=np.float64)
        self.T_machine_camera = np.zeros(3, dtype=np.float64)
        self.offset = (0, -20, 0)

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------

    @abstractmethod
    def get_image(self) -> np.ndarray:
        """Return a BGR image as a numpy array."""

    # ------------------------------------------------------------------
    # Motion
    # ------------------------------------------------------------------

    def move_to_get_image(self, x_depart, y_depart, z_depart) -> None:
        active_tool = self.tool_changer.get_active_tool_index()
        if active_tool == -1:
            active_tool_offset = (0, 0, 0)
        else:
            active_tool_offset = self.tool_changer.get_tool_offset(active_tool)

        x = x_depart + active_tool_offset[0]
        y = y_depart + active_tool_offset[1]
        z = z_depart + active_tool_offset[2]
        self.driver.move_to({"Z": float(z)}, s=600)
        self.driver.move_to({"X": float(x), "Y": float(y)}, s=800)

        position = self.driver.get_positions()
        self.T_machine_camera = np.array(
            [
                position["X"] - active_tool_offset[0] - self.offset[0],
                position["Y"] - active_tool_offset[1] - self.offset[1],
                -position["Z"] - active_tool_offset[2] - self.offset[2],
            ],
            dtype=np.float64,
        )

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def save_image(self, img=None, save_dir: Path = Path("."), save_name=None) -> None:
        if img is None:
            img = self.get_image()
        if save_name is None:
            save_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        cv2.imwrite(str(save_dir / f"{save_name}.jpg"), img)

    # ------------------------------------------------------------------
    # Multi-lighting acquisition
    # ------------------------------------------------------------------

    def get_multi_lighting_img(
        self,
        leds: "Neopixel",
        nb_img: int = 8,
        temp_dir: Path = Path("."),
    ) -> list:
        leds.all_pixel_off()
        for file in temp_dir.glob("*.jpg"):
            file.unlink()

        images = []
        for i in range(nb_img):
            logger.debug("LED %d", i % nb_img)
            leds.pixel_on(i % nb_img, 255, 255, 50)
            time.sleep(3)
            img = self.get_image()
            images.append(img)
            self.save_image(img=img, save_dir=temp_dir)
            leds.pixel_off(i)
            time.sleep(0.2)

        return images

    def get_clean_image(
        self,
        leds: Optional["Neopixel"] = None,
        images: Optional[list] = None,
        save_dir=None,
        save_name=None,
        nb_image_used: int = 8,
    ) -> np.ndarray:
        if images is None:
            if leds is None:
                raise ValueError("leds required when images is not provided")
            images = self.get_multi_lighting_img(leds=leds, nb_img=nb_image_used)

        if not images:
            raise ValueError("No images provided")

        result = images[0].copy()
        for img in images[1:]:
            result = np.minimum(result, img)

        if save_dir is not None:
            self.save_image(img=result, save_dir=save_dir, save_name=save_name)

        return result
