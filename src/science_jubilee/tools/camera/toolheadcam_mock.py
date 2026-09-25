from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

from science_jubilee.tools.camera.base import BaseCamera


@dataclass
class MockCameraResponse:
    """Small response object matching the parts of requests.Response we use."""

    status_code: int = 200

    def raise_for_status(self) -> None:
        return None


class ToolheadCamMock(BaseCamera):
    """In-memory camera for tests and offline use.

    Returns the injected image if provided, otherwise a blank black frame. Camera
    hardware methods are replaced by configurable in-memory mock behavior so the
    digital twin can exercise the same API as :class:`ToolheadCam` without HTTP.
    """

    DEFAULT_SHAPE = (720, 1280, 3)
    FOCUS_MODE_BY_NAME = {"manual": 0, "single": 1, "auto": 2}
    FOCUS_MODE_BY_VALUE = {0: "manual", 1: "single", 2: "auto"}
    DEFAULT_OPTION_DEFS = {
        "afmode": {
            "description": "[0..2]",
            "menu": {"0": "Manual", "1": "Auto", "2": "Continuous"},
            "name": "AfMode",
            "type": "integer",
        },
        "aftrigger": {
            "description": "[0..1]",
            "menu": {"0": "Start", "1": "Cancel"},
            "name": "AfTrigger",
            "type": "integer",
        },
        "lensposition": {
            "description": "[0.000000..15.000000]",
            "name": "LensPosition",
            "type": "float",
        },
    }
    DEFAULT_OPTION_VALUES = {
        "afmode": 2,
        "aftrigger": 0,
        "lensposition": 12.0,
    }

    def __init__(
        self,
        motion,
        tool_changer,
        image: Optional[np.ndarray] = None,
        calib_file=None,
        image_provider: Optional[Callable[[], np.ndarray]] = None,
        status_provider: Optional[Callable[[], dict[str, Any]]] = None,
        keep_alive_handler: Optional[Callable[[float], None]] = None,
    ) -> None:
        super().__init__(motion, tool_changer, calib_file=calib_file)
        self._image = image
        self._image_provider = image_provider
        self._status_provider = status_provider
        self._keep_alive_handler = keep_alive_handler
        self._option_values = copy.deepcopy(self.DEFAULT_OPTION_VALUES)

    def set_mock_image(self, image: Optional[np.ndarray]) -> None:
        """Force future captures to return ``image`` instead of a blank frame."""
        self._image = image

    def set_mock_image_provider(
        self, provider: Optional[Callable[[], np.ndarray]]
    ) -> None:
        """Force future captures to call ``provider`` for dynamic images.

        The provider is a callback that returns the image to use each time
        ``get_image()`` is called. For the digital twin, this can be a Blender
        render/snapshot call, for example a wrapper around::

            jubilee-twin snapshot --x 150 --y 150 --z 300 --pop

        That lets the mock camera return a fresh simulated camera frame instead
        of a fixed in-memory image.
        """
        self._image_provider = provider

    def set_mock_status_provider(
        self, provider: Optional[Callable[[], dict[str, Any]]]
    ) -> None:
        """Force ``get_status`` to return a caller-provided status document."""
        self._status_provider = provider

    def set_mock_option(self, key: str, value: Any) -> None:
        """Force one mock camera option value."""
        self._option_values[self._option_key(key)] = value

    def get_image(self) -> np.ndarray:
        if self._image_provider is not None:
            return self._image_provider().copy()
        if self._image is not None:
            return self._image.copy()
        return np.zeros(self.DEFAULT_SHAPE, dtype=np.uint8)

    def get_status(self) -> dict[str, Any]:
        """Return a webcam/status-shaped mock status document."""
        if self._status_provider is not None:
            return copy.deepcopy(self._status_provider())

        options = {}
        for key, option_def in self.DEFAULT_OPTION_DEFS.items():
            option = copy.deepcopy(option_def)
            option["value"] = self._status_value(key, self._option_values[key])
            options[key] = option

        return {
            "devices": [
                {
                    "allow_dma": True,
                    "captures": [],
                    "name": "CAMERA",
                    "options": options,
                    "output": False,
                    "path": "mock://camera",
                    "properties": {},
                }
            ],
            "endpoints": {
                "snapshot": {"enabled": True, "uri": "mock://snapshot"},
                "stream": {"enabled": True, "uri": "mock://stream"},
            },
            "outputs": {},
            "revision": "mock",
            "version": "mock",
        }

    def get_option(self, key: str) -> Any:
        """Return a mock camera option value."""
        option_key = self._option_key(key)
        if option_key not in self._option_values:
            raise RuntimeError(f"Could not find camera option {key!r} in mock camera.")
        return self._option_values[option_key]

    def set_option(self, key: str, value: Any) -> MockCameraResponse:
        """Set a mock camera option value."""
        self.set_mock_option(key, value)
        return MockCameraResponse()

    def keep_alive(self, seconds: float = 3) -> None:
        """Mock stream keep-alive hook."""
        if self._keep_alive_handler is not None:
            self._keep_alive_handler(seconds)

    def focus_mode(self, mode: str) -> None:
        """Set the mock camera focus mode."""
        if mode not in self.FOCUS_MODE_BY_NAME:
            raise ValueError(
                f"Focus mode must be one of {list(self.FOCUS_MODE_BY_NAME)}."
            )
        self.set_option("AfMode", self.FOCUS_MODE_BY_NAME[mode])

    def get_focus_mode(self) -> str:
        """Get the mock camera focus mode."""
        value = self.get_option("AfMode")
        try:
            return self.FOCUS_MODE_BY_VALUE[value]
        except KeyError:
            raise RuntimeError(f"Unknown camera AfMode value: {value}")

    def lens_position(self, position: int) -> None:
        """Set the mock camera lens position."""
        if not (0 <= position <= 12):
            raise ValueError("Lens position must be between 0 and 12.")
        self.set_option("LensPosition", position)

    def trigger_focus(self, focus_seconds: float = 3) -> None:
        """Trigger mock autofocus only when in single-focus mode."""
        af_mode = self.get_option("AfMode")
        if af_mode != 1:
            raise RuntimeError(
                "trigger_focus is only available when AfMode is 1 "
                "(single focus mode). Call focus_mode('single') before "
                f"trigger_focus(). Current AfMode is {af_mode}."
            )
        self.keep_alive(focus_seconds)
        self.set_option("AfTrigger", 0)

    def autofocus(self, focus_seconds: float = 3) -> np.ndarray:
        """Trigger mock autofocus, then return an image."""
        self.trigger_focus(focus_seconds=focus_seconds)
        return self.get_image()

    def _option_key(self, key: str) -> str:
        return key.lower()

    def _status_value(self, key: str, value: Any) -> Any:
        option = self.DEFAULT_OPTION_DEFS[key]
        if "menu" in option:
            return option["menu"].get(str(value), value)
        if option.get("type") == "float":
            return f"{float(value):.6f}"
        return value
