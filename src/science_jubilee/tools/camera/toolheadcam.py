from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

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
        self.stream_url = f"http://{address}/webcam/?action=stream"
        self.param_url = f"http://{address}/webcam/option?"
        self.status_url = f"http://{address}/webcam/status"
        self._af_mode: int | None = None
        self.focus_mode("auto")

    def get_image(self) -> np.ndarray:
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            img = cv2.imdecode(
                np.frombuffer(response.content, np.uint8),
                cv2.IMREAD_COLOR,
            )
            img = img[:, :, ::-1]  # Convert BGR to RGB
            if img is None:
                raise RuntimeError("Could not decode image from camera response.")
            return img
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Camera connection error: {e}")

    def set_option(self, key: str, value: int) -> requests.Response:
        """Set an mjpeg-streamer camera option."""
        response = requests.get(f"{self.param_url}key={key}&value={value}", timeout=10)
        if key == "AfMode":
            self._af_mode = value
        logger.info(f"Camera response: {response.status_code}")
        return response

    def get_status(self) -> dict[str, Any]:
        """Get the full webcam status document."""
        response = requests.get(self.status_url, timeout=10)
        response.raise_for_status()
        return response.json()

    def get_option(self, key: str) -> Any:
        """Get a camera option value from the webcam status endpoint."""
        status = self.get_status()

        option_key = key.lower()
        option = None
        for device in status.get("devices", []):
            options = device.get("options", {})
            if option_key in options:
                option = options[option_key]
                break

        if option is None:
            raise RuntimeError(
                f"Could not find camera option {key!r} in webcam status."
            )

        if "value" not in option:
            raise RuntimeError(f"Camera option {key!r} does not report a value.")

        value = option["value"]
        menu = option.get("menu", {})
        if menu:
            value_by_label = {label: int(number) for number, label in menu.items()}
            if value in value_by_label:
                value = value_by_label[value]
        elif option.get("type") in {"integer", "integer64"}:
            match = re.search(r"-?\d+", str(value))
            if match is None:
                raise RuntimeError(
                    f"Could not parse camera option {key!r} value: {value!r}"
                )
            value = int(match.group(0))
        elif option.get("type") == "float":
            value = float(value)
        elif option.get("type") == "bool":
            value = str(value).lower() in {"1", "true"}

        if option_key == "afmode":
            self._af_mode = value
        logger.info(f"Camera option {key} is {value}")
        return value

    def keep_alive(self, seconds: float = 3) -> None:
        """Keep the camera stream open long enough for autofocus to settle."""
        with requests.get(
            self.stream_url, stream=True, timeout=seconds + 2
        ) as response:
            response.raise_for_status()
            start = time.time()
            for _ in response.iter_content(4096):
                if time.time() - start > seconds:
                    break

    def autofocus(self, focus_seconds: float = 3) -> np.ndarray:
        """Trigger autofocus, then return an image."""
        self.trigger_focus(focus_seconds=focus_seconds)
        return self.get_image()

    def focus_mode(self, mode: str) -> None:
        """Set the camera focus mode."""
        mode = self.normalize_focus_mode(mode)
        value_by_mode = {"manual": 0, "single": 1, "auto": 2}
        response = self.set_option("AfMode", value_by_mode[mode])
        if mode == "manual":
            logger.info("in manual mode, use lensPosition parameter to adjust focus")
        elif mode == "single":
            logger.info(
                "in single focus mode, the camera will focus once and then hold: use trigger_focus to refocus if needed"
            )
        elif mode == "auto":
            logger.info(
                "in auto focus mode, the camera will continuously adjust focus automatically"
            )
        logger.info(f"Camera response: {response.status_code}")
        logger.info(f"Setting focus mode to {mode}")

    def trigger_single_autofocus(self, focus_seconds: float = 3) -> None:
        """Switch to single-focus mode and trigger one autofocus cycle.

        Some camera status endpoints report the previous continuous-focus mode
        briefly after changing AfMode. For a scan, the safest behavior is to set
        AfMode immediately before triggering and trust the successful option
        request instead of failing on a stale status read.
        """
        self.focus_mode("single")
        self._trigger_focus(focus_seconds=focus_seconds)

    def get_focus_mode(self) -> str:
        """Get the current camera focus mode from the camera."""
        mode_by_value = {0: "manual", 1: "single", 2: "auto"}
        value = self.get_option("AfMode")
        try:
            return mode_by_value[value]
        except KeyError:
            raise RuntimeError(f"Unknown camera AfMode value: {value}")

    def lens_position(self, position: int) -> None:
        """Set the camera lens position (only applicable in manual focus mode)."""
        if not (0 <= position <= 12):
            raise ValueError("Lens position must be between 0 and 12.")
        response = self.set_option("LensPosition", position)
        logger.info(f"Camera response: {response.status_code}")
        logger.info(f"Setting lens position to {position}")

    def trigger_focus(self, focus_seconds: float = 3) -> None:
        """Trigger the camera to refocus in single-focus mode.

        The mjpeg stream is kept open while autofocus runs so the camera has
        live frames to focus from. After ``focus_seconds`` seconds, focus is
        complete and the caller can capture an image with ``get_image()``.
        """
        af_mode = self.get_option("AfMode")
        if af_mode != 1:
            raise RuntimeError(
                "trigger_focus is only available when AfMode is 1 "
                "(single focus mode). Call focus_mode('single') before "
                f"trigger_focus(). Current AfMode is {af_mode}."
            )
        self._trigger_focus(focus_seconds=focus_seconds)

    def _trigger_focus(self, focus_seconds: float = 3) -> None:
        """Send the hardware focus trigger once AfMode has been prepared."""
        keep_alive_thread = threading.Thread(
            target=self.keep_alive,
            kwargs={"seconds": focus_seconds},
        )
        keep_alive_thread.start()
        time.sleep(1)
        response = self.set_option("AfTrigger", 0)
        keep_alive_thread.join()
        logger.info(f"Camera response: {response.status_code}")
        logger.info("Triggered camera to refocus")
