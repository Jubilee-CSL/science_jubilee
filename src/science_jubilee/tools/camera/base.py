from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np
import yaml


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

    def get_parameters(self) -> dict[str, Any]:
        """Return the camera's current parameter/status document if available."""
        get_status = getattr(self, "get_status", None)
        return get_status() if callable(get_status) else {}

    def get_machine_status(self) -> dict[str, Any]:
        """Return the current machine status associated with this camera."""
        transport = getattr(getattr(self, "driver", None), "transport", None)
        if transport is None:
            return {}
        try:
            return transport.get_machine_summary()
        except Exception:
            positions = getattr(self.driver, "get_positions", lambda: {})()
            axes = getattr(self.driver, "get_available_axes", lambda: [])()
            return {"positions": positions, "axes": axes}

    def save_acquisition_metadata(
        self,
        save_dir: Path = Path("."),
        save_name: str | None = None,
        image_name: str | None = None,
    ) -> str:
        """Save camera parameters and machine status next to an acquired image."""
        if save_name is None:
            save_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        if image_name is None:
            image_name = f"{save_name}.jpg"
        payload = {
            "image": image_name,
            "queried_at": datetime.now(timezone.utc).isoformat(),
            "camera_parameters": self.get_parameters(),
            "machine_status": self.get_machine_status(),
        }
        path = save_dir / f"{save_name}.camera.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        return str(path)

    def normalize_focus_mode(self, mode: str) -> str:
        """Normalize user-facing focus mode aliases."""
        normalized = str(mode).strip().lower()
        aliases = {
            "autofocus": "auto",
            "continuous": "auto",
            "continuous_autofocus": "auto",
        }
        normalized = aliases.get(normalized, normalized)
        if normalized not in {"manual", "single", "auto"}:
            raise ValueError(
                "focus mode must be one of 'manual', 'single', 'auto', or 'autofocus'"
            )
        return normalized

    def configure_focus(
        self,
        mode: str,
        lens_position: Optional[int] = None,
    ) -> str:
        """Configure camera focus mode when the camera supports focus controls.

        Cameras that do not expose focus controls accept ``auto`` as a no-op.
        ``manual`` requires a lens position and ``single`` prepares the camera
        for a later single-autofocus trigger.
        """
        normalized = self.normalize_focus_mode(mode)
        set_focus_mode = getattr(self, "focus_mode", None)
        if set_focus_mode is None:
            if normalized == "auto":
                return normalized
            raise NotImplementedError(
                f"{type(self).__name__} does not support focus_mode={normalized!r}"
            )

        set_focus_mode(normalized)
        if normalized == "manual":
            if lens_position is None:
                raise ValueError("lens_position is required when focus_mode='manual'")
            set_lens_position = getattr(self, "lens_position", None)
            if set_lens_position is None:
                raise NotImplementedError(
                    f"{type(self).__name__} does not support manual lens position"
                )
            set_lens_position(int(lens_position))

        return normalized

    def trigger_single_autofocus(self, focus_seconds: float = 3) -> None:
        """Prepare single-focus mode and trigger one autofocus cycle."""
        self.configure_focus("single")
        trigger_focus = getattr(self, "trigger_focus", None)
        if trigger_focus is None:
            raise NotImplementedError(
                f"{type(self).__name__} does not support single autofocus trigger"
            )
        trigger_focus(focus_seconds=focus_seconds)

    def autofocus(self, focus_seconds: float = 3) -> np.ndarray:
        """Focus the camera if supported, then return a RGB image.

        Camera implementations without controllable focus fall back to a normal
        image capture. ``focus_seconds`` is accepted for API compatibility.
        """
        return self.get_image()

    # ------------------------------------------------------------------
    # Motion
    # ------------------------------------------------------------------

    def move_to_get_image(self, x_depart, y_depart, z_depart) -> None:
        active_tool = self.tool_changer.get_active_tool_index()
        if active_tool == -1:
            active_tool_offset = (0, 0, 0)
        else:
            active_tool_offset = self.tool_changer.get_tool_offset(active_tool)

        x = x_depart + active_tool_offset[0] + self.offset[0]
        y = y_depart + active_tool_offset[1] + self.offset[1]
        z = z_depart + active_tool_offset[2] + self.offset[2]
        self.driver.move_to({"Z": float(z)}, s=600)
        self.driver.move_to({"X": float(x), "Y": float(y)}, s=800)

        self.driver.get_positions()

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def save_image(self, img=None, save_dir: Path = Path("."), save_name=None) -> None:
        if img is None:
            img = self.get_image()
        if save_name is None:
            save_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        cv2.imwrite(str(save_dir / f"{save_name}.jpg"), img)
