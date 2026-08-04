"""MachineSession: single-object entry point for the science-jubilee stack.

Usage examples::

    # Mock (no hardware required)
    session = MachineSession.mock(deck_def="lab_automation_deck_AFL_bolton.json")
    session.motion.move_to({"X": 100, "Y": 50})

    # Hardware
    session = MachineSession.hardware(
        "192.168.1.2",
        deck_def="lab_automation_deck_AFL_bolton.json",
    )

    # From a .env file
    session = MachineSession.from_env(".env.mock")

    # Context manager
    with MachineSession.mock() as s:
        s.motion.home_all()
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class MachineSession:
    """Wires transport → motion → tool_changer → navigator into one object."""

    def __init__(self, transport, deck_def: Optional[str] = None, camera_address: Optional[str] = None, led_address: Optional[str] = None) -> None:
        from science_jubilee.hal.motion_driver import MotionDriver
        from science_jubilee.hal.tool_changer import ToolChanger

        self.transport = transport
        self.motion = MotionDriver(transport)
        self.tool_changer = ToolChanger(transport)

        if deck_def is not None:
            from science_jubilee.decks.Deck import Deck
            from science_jubilee.navigation.deck_navigation import DeckNavigator

            self.navigator: Optional[object] = DeckNavigator(
                driver=self.motion, deck=Deck(deck_def)
            )
        else:
            self.navigator = None

        if camera_address is not None:
            from science_jubilee.tools.camera.hardware import Camera
            self.camera = Camera(
                motion=self.motion, tool_changer=self.tool_changer,
                address=camera_address,
            )
        else:
            from science_jubilee.tools.camera.mock import MockCamera
            self.camera = MockCamera(
                motion=self.motion, tool_changer=self.tool_changer,
            )

        if led_address is not None:
            from science_jubilee.tools.Neopixel import Neopixel
            self.neopixel: Optional[object] = Neopixel(url=f"http://{led_address}:5001")
        else:
            self.neopixel = None

    # ------------------------------------------------------------------
    # Factory classmethods
    # ------------------------------------------------------------------

    @classmethod
    def mock(
        cls,
        deck_def: Optional[str] = None,
        log_path: str = "gcode_logs/latest.gcode",
        camera_address: Optional[str] = None,
        led_address: Optional[str] = None,
    ) -> "MachineSession":
        """Build a session backed by the in-memory MockTransport."""
        from science_jubilee.hal.transport.mock import MockTransport
        from science_jubilee.hal.transport.recording import RecordingTransport

        transport = RecordingTransport(MockTransport(), log_path=log_path)
        return cls(transport, deck_def=deck_def, camera_address=camera_address, led_address=led_address)

    @classmethod
    def hardware(
        cls,
        address: str,
        deck_def: Optional[str] = None,
        log_path: str = "gcode_logs/latest.gcode",
        deck_clear_provider: Optional[Callable[[], bool]] = None,
        camera_address: Optional[str] = None,
        led_address: Optional[str] = None,
    ) -> "MachineSession":
        """Build a session connected to a real Duet/RRF machine."""
        from science_jubilee.hal.transport.http import HTTPTransport
        from science_jubilee.hal.transport.recording import RecordingTransport

        if deck_clear_provider is None:
            deck_clear_provider = lambda: True
        transport = RecordingTransport(
            HTTPTransport(address=address, deck_clear_provider=deck_clear_provider),
            log_path=log_path,
        )
        return cls(transport, deck_def=deck_def, camera_address=camera_address, led_address=led_address)

    @classmethod
    def from_env(
        cls,
        env_file: Optional[str] = None,
        deck_def: Optional[str] = None,
    ) -> "MachineSession":
        """Build a session from environment variables (optionally loading a .env file).

        Reads:
          JUBILEE_TRANSPORT      — ``mock`` (default) or ``hardware``
          JUBILEE_ADDRESS        — machine IP, required when transport=hardware
          JUBILEE_DECK_DEF       — deck definition filename (overridden by *deck_def* arg)
          JUBILEE_GCODE_LOG      — G-code log path (default: gcode_logs/latest.gcode)
          JUBILEE_CAMERA_ADDRESS — OctoPi/camera IP; omit to skip camera wiring
          JUBILEE_NEOPIXEL_ADDRESS — LED server IP; omit to skip Neopixel wiring
          JUBILEE_RAW_DIR          — directory for raw images (default: dataset_brut)
          JUBILEE_LED_DIR          — directory for multi-lighting images (default: dataset_brut_led)
        """
        if env_file is not None:
            from science_jubilee.utils.env import load_env_file

            load_env_file(env_file)

        transport_type = os.getenv("JUBILEE_TRANSPORT", "mock").strip().lower()
        address = os.getenv("JUBILEE_ADDRESS")
        log_path = os.getenv("JUBILEE_GCODE_LOG", "gcode_logs/latest.gcode")

        if deck_def is None:
            deck_def = os.getenv("JUBILEE_DECK_DEF") or None

        camera_address = os.getenv("JUBILEE_CAMERA_ADDRESS") or None
        led_address = os.getenv("JUBILEE_NEOPIXEL_ADDRESS") or None

        if transport_type == "hardware":
            if not address:
                raise ValueError(
                    "JUBILEE_ADDRESS must be set (or passed via --jubilee-address) "
                    "when JUBILEE_TRANSPORT=hardware"
                )
            return cls.hardware(address=address, deck_def=deck_def, log_path=log_path, camera_address=camera_address, led_address=led_address)

        return cls.mock(deck_def=deck_def, log_path=log_path, camera_address=camera_address, led_address=led_address)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "MachineSession":
        return self

    def __exit__(self, *_) -> None:
        pass

    def __repr__(self) -> str:
        nav = f", navigator={self.navigator!r}" if self.navigator else ""
        cam = f", camera={self.camera!r}" if self.camera else ""
        neo = f", neopixel={self.neopixel!r}" if self.neopixel else ""
        return f"MachineSession(transport={self.transport!r}{nav}{cam}{neo})"
