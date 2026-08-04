from __future__ import annotations

import logging

import cv2
import numpy as np
import requests

from science_jubilee.tools.camera.base import BaseCamera

logger = logging.getLogger(__name__)


class ToolheadCam(BaseCamera):
    """OctoPi/mjpeg-streamer camera over HTTP."""

    def __init__(self, motion, tool_changer, address: str, calib_file=None) -> None:
        super().__init__(motion, tool_changer, calib_file=calib_file)
        self.url = f"http://{address}/webcam/?action=snapshot"

    def get_image(self) -> np.ndarray:
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            img = cv2.imdecode(
                np.frombuffer(response.content, np.uint8),
                cv2.IMREAD_COLOR,
            )
            if img is None:
                raise RuntimeError("Could not decode image from camera response.")
            return img
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Camera connection error: {e}")
