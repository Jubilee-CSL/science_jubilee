from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import yaml

logger = logging.getLogger(__name__)


class BaseCamera(ABC):
    """Abstract camera interface.

    Subclasses implement get_image(); all other methods are shared.
    """

    def __init__(self, motion, tool_changer, calib_file: Optional[str] = None) -> None:
        self.driver = motion
        self.tool_changer = tool_changer

        self.K: Optional[np.ndarray] = None
        self.dist: Optional[np.ndarray] = None
        self.offset: tuple = (0, 0, 0)
        self.R_machine_camera = np.eye(3, dtype=np.float64)
        self.T_machine_camera = np.zeros(3, dtype=np.float64)

        if calib_file is not None:
            self._load_calibration(calib_file)

    def _load_calibration(self, path: str) -> None:
        """Load intrinsics and offset from a camera_params.yaml produced by calibrate_camera.py."""
        with open(path, "r") as f:
            cfg = yaml.safe_load(f)
        c = cfg["camera"]
        self.K = np.array(
            [[c["fx"], 0, c["cx"]], [0, c["fy"], c["cy"]], [0, 0, 1]],
            dtype=np.float64,
        )
        self.dist = np.array(c["dist"], dtype=np.float64)
        self.offset = tuple(c.get("offset", [0, 0, 0]))

    def _require_calibration(self) -> None:
        if self.K is None or self.dist is None:
            raise RuntimeError(
                "Camera intrinsics not loaded. "
                "Pass calib_file= or set JUBILEE_CAMERA_CALIB."
            )

    # ------------------------------------------------------------------
    # Abstract
    # ------------------------------------------------------------------

    @abstractmethod
    def get_image(self) -> np.ndarray:
        """Return a RGB image as a numpy array."""

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
        img_out = cv2.cvtColor(img,cv2.COLOR_BGR2RGB)
        cv2.imwrite(str(save_dir / f"{save_name}.jpg"), img_out)
