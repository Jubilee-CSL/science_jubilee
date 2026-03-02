import os
import re
import sys
from pathlib import Path
from typing import Optional, Any, Dict

from .base import BaseTransport


class RecordingTransport(BaseTransport):
    """Wrapper transport that logs all G-code commands to a file and forwards
    them to an underlying transport (mock or hardware).

    This is intended for generating G-code files that can be visualized
    elsewhere (e.g., in OctoPrint's G-code viewer) while still using the
    existing transport implementations for simulation or hardware.
    """

    def __init__(self, inner: BaseTransport, log_path: Optional[str] = None):
        self._inner = inner
        # Default log path can be overridden via env
        if log_path is None:
            log_path = os.getenv("JUBILEE_GCODE_LOG", "gcode_logs/latest.gcode")
        self.log_path = Path(log_path)
        self.run_log_path = self._resolve_run_log_path()
        try:
            for p in self._iter_log_paths():
                p.parent.mkdir(parents=True, exist_ok=True)
            # Start a fresh log for this session and seed with a tiny
            # synthetic extrusion segment so that viewers like OctoPrint's
            # G-code viewer detect at least one printable path. This is
            # written ONLY to the log file and is NOT sent to the
            # underlying transport.
            seed = (
                "; visualization seed added by RecordingTransport\n"
                "G90\n"              # absolute positioning
                "M82\n"              # absolute extrusion
                "G92 X0 Y0 Z0 E0\n"
                "G1 X0.10 Y0.00 E0.10 F600\n"  # short extrusion move
            )
            for p in self._iter_log_paths():
                p.write_text(seed, encoding="utf-8")
        except Exception:
            # Logging should never break transport use
            pass

    def _iter_log_paths(self) -> list[Path]:
        paths = [self.log_path]
        if self.run_log_path is not None and self.run_log_path != self.log_path:
            paths.append(self.run_log_path)
        return paths

    @staticmethod
    def _sanitize_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name)).strip("._-")
        return cleaned or "session"

    def _resolve_run_log_path(self) -> Optional[Path]:
        # Priority: explicit copy path > explicit run name > pytest test file > __main__ file
        if copy := os.getenv("JUBILEE_GCODE_LOG_COPY"):
            return Path(copy)

        run_name = (
            os.getenv("JUBILEE_RUN_NAME", "").strip()
            or self._name_from_pytest()
            or self._name_from_main()
        )
        if not run_name:
            return None
        suffix = self.log_path.suffix or ".gcode"
        return self.log_path.with_name(f"{self._sanitize_name(run_name)}{suffix}")

    @staticmethod
    def _name_from_pytest() -> str:
        """Return the test file stem from PYTEST_CURRENT_TEST if set.

        pytest sets this automatically to e.g.:
          tests/test_navigation_deck.py::test_move_to_well (call)
        """
        val = os.getenv("PYTEST_CURRENT_TEST", "")
        return Path(val.split("::")[0]).stem if val else ""

    @staticmethod
    def _name_from_main() -> str:
        """Return the stem of __main__.__file__ for plain script execution."""
        main_file = getattr(sys.modules.get("__main__"), "__file__", None)
        return Path(main_file).stem if main_file else ""

    # Expose address if the inner transport has one (used by machine summary)
    @property
    def address(self) -> Optional[str]:
        return getattr(self._inner, "address", None)

    def _log(self, cmd: str) -> None:
        try:
            if cmd is None:
                return
            s = str(cmd).rstrip()
            if not s:
                return
            for p in self._iter_log_paths():
                with p.open("a", encoding="utf-8") as f:
                    f.write(s + "\n")
        except Exception:
            # Swallow logging errors to avoid affecting motion
            pass

    # ---- Core transport methods ---------------------------------------
    def send_gcode(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False):
        # Record every command that goes through the transport
        self._log(cmd)
        return self._inner.send_gcode(cmd=cmd, timeout=timeout, response_wait=response_wait, wait=wait)

    def connect(self, timeout: Optional[float] = 5.0) -> bool:
        return self._inner.connect(timeout=timeout)

    def deck_is_clear(self) -> bool:
        return self._inner.deck_is_clear()

    # ---- Tools API -----------------------------------------------------
    def get_active_tool_index(self) -> int:
        return self._inner.get_active_tool_index()

    def select_tool(self, index: int) -> bool:
        # Tool commands also get logged via send_gcode, so just delegate
        return self._inner.select_tool(index)

    def park_tool(self) -> bool:
        return self._inner.park_tool()

    def get_tools(self) -> Dict[int, Dict[str, Any]]:
        return self._inner.get_tools()

    def get_tool_offsets(self) -> Dict[int, list[float]]:
        return self._inner.get_tool_offsets()

    def set_tool_offset(self, tool_idx: int, *, x: float | None = None, y: float | None = None, z: float | None = None) -> bool:
        return self._inner.set_tool_offset(tool_idx, x=x, y=y, z=z)

    # ---- Convenience: axes/limits/positions ---------------------------
    def get_available_axes(self) -> list:
        return self._inner.get_available_axes()

    def get_axis_limits(self) -> dict:
        return self._inner.get_axis_limits()

    def get_positions(self) -> dict:
        return self._inner.get_positions()
