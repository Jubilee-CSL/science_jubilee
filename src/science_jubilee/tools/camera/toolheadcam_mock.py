from __future__ import annotations

from typing import Optional

import numpy as np

from science_jubilee.tools.camera.base import BaseCamera


class ToolheadCamMock(BaseCamera):
    """In-memory camera for tests and offline use.

    Returns the injected image if provided, otherwise a blank black frame.
    """

    DEFAULT_SHAPE = (720, 1280, 3)

    def __init__(self, motion, tool_changer, image: Optional[np.ndarray] = None, calib_file=None) -> None:
        super().__init__(motion, tool_changer, calib_file=calib_file)
        self._image = image

    def get_image(self) -> np.ndarray:
        if self._image is not None:
            return self._image.copy()
        return np.zeros(self.DEFAULT_SHAPE, dtype=np.uint8)
