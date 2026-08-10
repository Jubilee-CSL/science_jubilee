"""MachineSession: single-object entry point for the science-jubilee stack.

The recommended workflow is to keep all experiment-specific files (deck.json,
labware JSONs, gcode files) in one folder and point JUBILEE_EXPERIMENT_DIR at it.

Usage examples::

    # From a .env file (recommended)
    # .env contains: JUBILEE_EXPERIMENT_DIR, JUBILEE_DECK_DEF, JUBILEE_TRANSPORT, ...
    session = MachineSession.from_env(".env.mock")
    session.free_navigator.move_to(x=100, y=50)
    session.navigator.move_to_well(slot="0", well="A1")

    # Mock with explicit experiment folder
    session = MachineSession.mock(
        deck_def="deck",
        experiment_dir=Path("/path/to/my_experiment"),
    )

    # Hardware with explicit experiment folder
    session = MachineSession.hardware(
        "192.168.1.2",
        deck_def="deck",
        experiment_dir=Path("/path/to/my_experiment"),
    )

    # Context manager
    with MachineSession.from_env(".env.mock") as s:
        s.motion.home_all()
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from science_jubilee.tools.light.base import BaseLight

logger = logging.getLogger(__name__)


class MachineSession:
    """Wires transport → motion → tool_changer → navigator into one object."""

    def __init__(
        self,
        transport,
        use_mock: bool = True,
        deck_def: Optional[str] = None,
        camera_address: Optional[str] = None,
        led_address: Optional[str] = None,
        camera_calib: Optional[str] = None,
        experiment_dir: Optional[Path] = None,
    ) -> None:
        """Wire transport, motion, tool-changer, navigator, camera, and light into one session.

        Args:
            transport: Pre-built transport layer (e.g. ``RecordingTransport(MockTransport())``).
            use_mock: When ``True`` use ``ToolheadCamMock`` and ``NeopixelMock``; when
                ``False`` connect to real hardware using ``camera_address`` and ``led_address``.
            deck_def: Stem of the deck JSON file (e.g. ``"deck"`` resolves to ``deck.json``).
                Defaults to ``"deck"`` when ``experiment_dir`` contains ``deck.json``.
            camera_address: Hostname or IP of the camera server (required when ``use_mock=False``).
            led_address: Hostname or IP of the Neopixel LED server (required when ``use_mock=False``).
            camera_calib: Path to the ``camera_params.yaml`` produced by ``calibrate_camera.py``.
            experiment_dir: Folder containing ``deck.json``, labware JSONs, and G-code files.
                Passed as both ``path`` and ``labware_search_path`` to :class:`~science_jubilee.decks.Deck.Deck`.
        """
        from science_jubilee.hal.motion_driver import MotionDriver
        from science_jubilee.hal.tool_changer import ToolChanger

        self.transport = transport
        self.motion = MotionDriver(transport)
        self.tool_changer = ToolChanger(transport)
        self.experiment_dir: Optional[Path] = experiment_dir

        # always look for deck.json in experiment_dir
        if deck_def is None and experiment_dir is not None:
            if (experiment_dir / "deck.json").exists():
                deck_def = "deck"

        if deck_def is not None:
            from science_jubilee.decks.Deck import Deck
            from science_jubilee.navigation.deck_navigation import DeckNavigator

            deck_kwargs = {}
            if experiment_dir is not None:
                deck_kwargs["path"] = str(experiment_dir)
                deck_kwargs["labware_search_path"] = str(experiment_dir)

            self.navigator: Optional["DeckNavigator"] = DeckNavigator(
                driver=self.motion, deck=Deck(deck_def, **deck_kwargs)
            )
        else:
            self.navigator = None

        if use_mock:
            from science_jubilee.tools.camera.toolheadcam_mock import ToolheadCamMock
            from science_jubilee.tools.light.neopixel_mock import NeopixelMock

            self.camera = ToolheadCamMock(
                motion=self.motion,
                tool_changer=self.tool_changer,
                calib_file=camera_calib,
            )
            self.light: BaseLight = NeopixelMock()
        else:
            if not camera_address:
                raise ValueError(
                    "JUBILEE_CAMERA_ADDRESS required for hardware transport"
                )
            if not led_address:
                raise ValueError(
                    "JUBILEE_NEOPIXEL_ADDRESS required for hardware transport"
                )
            from science_jubilee.tools.camera.toolheadcam import ToolheadCam
            from science_jubilee.tools.light.neopixel import Neopixel

            self.camera = ToolheadCam(
                motion=self.motion,
                tool_changer=self.tool_changer,
                address=camera_address,
                calib_file=camera_calib,
            )
            self.light = Neopixel(url=f"http://{led_address}:5001")

    # ------------------------------------------------------------------
    # Factory classmethods
    # ------------------------------------------------------------------

    @classmethod
    def mock(
        cls,
        deck_def: Optional[str] = None,
        log_path: str = "gcode_logs/latest.gcode",
        camera_calib: Optional[str] = None,
        experiment_dir: Optional[Path] = None,
    ) -> "MachineSession":
        """Build a session backed by the in-memory ``MockTransport``.

        Args:
            deck_def: Stem of the deck JSON file; auto-detected from ``experiment_dir`` if omitted.
            log_path: Destination for the G-code recording log.
            camera_calib: Path to ``camera_params.yaml``; ``None`` skips calibration loading.
            experiment_dir: Folder containing deck and labware definitions.
        """
        from science_jubilee.hal.transport.mock import MockTransport
        from science_jubilee.hal.transport.recording import RecordingTransport

        transport = RecordingTransport(MockTransport(), log_path=log_path)
        return cls(
            transport,
            use_mock=True,
            deck_def=deck_def,
            camera_calib=camera_calib,
            experiment_dir=experiment_dir,
        )

    @classmethod
    def hardware(
        cls,
        address: str,
        deck_def: Optional[str] = None,
        log_path: str = "gcode_logs/latest.gcode",
        deck_clear_provider: Optional[Callable[[], bool]] = None,
        camera_address: Optional[str] = None,
        led_address: Optional[str] = None,
        camera_calib: Optional[str] = None,
        experiment_dir: Optional[Path] = None,
    ) -> "MachineSession":
        """Build a session connected to a real Duet/RRF machine over HTTP.

        Args:
            address: IP address or hostname of the Duet board.
            deck_def: Stem of the deck JSON file; auto-detected from ``experiment_dir`` if omitted.
            log_path: Destination for the G-code recording log.
            deck_clear_provider: Callable returning ``True`` when the deck is safe to move over.
                Defaults to a no-op lambda; supply a real probe callback for safety.
            camera_address: Hostname or IP of the camera server.
            led_address: Hostname or IP of the Neopixel LED server.
            camera_calib: Path to ``camera_params.yaml``; ``None`` skips calibration loading.
            experiment_dir: Folder containing deck and labware definitions.
        """
        from science_jubilee.hal.transport.http import HTTPTransport
        from science_jubilee.hal.transport.recording import RecordingTransport

        if deck_clear_provider is None:
            deck_clear_provider = (
                lambda: True
            )  # caller must supply a real probe if deck-clear checks are needed
        transport = RecordingTransport(
            HTTPTransport(address=address, deck_clear_provider=deck_clear_provider),
            log_path=log_path,
        )
        return cls(
            transport,
            use_mock=False,
            deck_def=deck_def,
            camera_address=camera_address,
            led_address=led_address,
            camera_calib=camera_calib,
            experiment_dir=experiment_dir,
        )

    @classmethod
    def from_env(
        cls,
        env_file: Optional[str] = None,
        deck_def: Optional[str] = None,
    ) -> "MachineSession":
        """Build a session from environment variables (optionally loading a .env file).

        Reads:
          JUBILEE_TRANSPORT        — ``mock`` (default) or ``hardware``
          JUBILEE_ADDRESS          — machine IP, required when transport=hardware
          JUBILEE_DECK_DEF         — deck JSON filename; auto-detected when experiment dir has exactly one .json
          JUBILEE_EXPERIMENT_DIR   — folder containing deck.json, labware JSONs, and gcode files
          JUBILEE_GCODE_LOG        — G-code log path (default: gcode_logs/latest.gcode)
          JUBILEE_CAMERA_ADDRESS   — OctoPi/camera IP; omit to skip camera wiring
          JUBILEE_NEOPIXEL_ADDRESS — LED server IP; omit to skip Neopixel wiring
          JUBILEE_CAMERA_CALIB     — path to camera_params.yaml from calibrate_camera.py
          JUBILEE_RAW_DIR          — directory for raw images (default: dataset_brut)
          JUBILEE_LED_DIR          — directory for multi-lighting images (default: dataset_brut_led)
        """
        if env_file is not None:
            from science_jubilee.utils.env import load_env_file

            path = Path(env_file)
            if not path.is_absolute():
                # resolve relative to cwd first, then repo root as fallback
                if not path.exists():
                    path = Path(__file__).resolve().parent.parent.parent / env_file
            if not path.exists():
                raise FileNotFoundError(f"env file not found: {env_file}")
            load_env_file(path, override=True)
            _env_dir = path.parent  # used to resolve relative paths in env values
        else:
            _env_dir = Path(__file__).resolve().parent.parent.parent

        transport_type = os.getenv("JUBILEE_TRANSPORT", "mock").strip().lower()
        address = os.getenv("JUBILEE_ADDRESS")
        log_path = os.getenv("JUBILEE_GCODE_LOG", "gcode_logs/latest.gcode")

        if deck_def is None:
            deck_def = os.getenv("JUBILEE_DECK_DEF") or None

        camera_address = os.getenv("JUBILEE_CAMERA_ADDRESS") or None
        led_address = os.getenv("JUBILEE_NEOPIXEL_ADDRESS") or None
        _calib = os.getenv("JUBILEE_CAMERA_CALIB") or None
        camera_calib = (
            str((_env_dir / _calib).resolve())
            if _calib and not Path(_calib).is_absolute()
            else _calib
        )
        _exp_dir = os.getenv("JUBILEE_EXPERIMENT_DIR") or None
        experiment_dir = (
            Path(_exp_dir)
            if (_exp_dir and Path(_exp_dir).is_absolute())
            else ((_env_dir / _exp_dir).resolve() if _exp_dir else None)
        )

        if transport_type == "hardware":
            if not address:
                raise ValueError(
                    "JUBILEE_ADDRESS must be set (or passed via --jubilee-address) "
                    "when JUBILEE_TRANSPORT=hardware"
                )
            return cls.hardware(
                address=address,
                deck_def=deck_def,
                log_path=log_path,
                camera_address=camera_address,
                led_address=led_address,
                camera_calib=camera_calib,
                experiment_dir=experiment_dir,
            )

        return cls.mock(
            deck_def=deck_def,
            log_path=log_path,
            camera_calib=camera_calib,
            experiment_dir=experiment_dir,
        )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def free_navigator(self):
        """A FreeNavigator wired to this session's motion and tool changer."""
        from science_jubilee.navigation.free_navigation import FreeNavigator

        return FreeNavigator(self.motion, self.tool_changer)

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "MachineSession":
        return self

    def __exit__(self, *_) -> None:
        pass

    def __repr__(self) -> str:
        nav = f", navigator={self.navigator!r}" if self.navigator else ""
        return f"MachineSession(transport={self.transport!r}, camera={self.camera!r}, light={self.light!r}{nav})"
