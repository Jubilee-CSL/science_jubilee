import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from science_jubilee._paths import jubilee_dir

from .base import BaseTransport

# Maximum depth for recursive M98 macro expansion (guards against circular includes)
_MAX_EXPAND_DEPTH = 5

_REPO_ROOT = jubilee_dir()
_DEFAULT_SYS_DIR = _REPO_ROOT / "firmware" / "sys"
_DEFAULT_MACRO_DIR = _REPO_ROOT / "firmware" / "macro"


class RecordingTransport(BaseTransport):
    """Wraps an inner transport, logging every G-code command to file.

    T{n} commands are expanded in the log into the full macro sequence
    (tfree, tpre, tpost). M98 calls are expanded recursively.
    """

    @property
    def is_mock(self) -> bool:  # type: ignore[override]
        return getattr(self._inner, "is_mock", False)

    def __init__(
        self,
        inner: BaseTransport,
        log_path: Optional[str] = None,
        *,
        sys_dir: Optional[Path] = _DEFAULT_SYS_DIR,
        macro_dir: Optional[Path] = _DEFAULT_MACRO_DIR,
    ):
        self._inner = inner
        self._sys_dir: Optional[Path] = Path(sys_dir) if sys_dir is not None else None
        self._macro_dir: Optional[Path] = (
            Path(macro_dir) if macro_dir is not None else None
        )

        # Default log path is derived; the location follows JUBILEE_PIPELINE_DATA.
        if log_path is None:
            from science_jubilee._paths import gcode_logs_dir

            log_path = str(gcode_logs_dir() / "latest.gcode")
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
                "G90\n"  # absolute positioning
                "M82\n"  # absolute extrusion
                "G92 X0 Y0 Z0 E0\n"
                "G1 X0.10 Y0.00 E0.10 F600\n"  # short extrusion move
            )
            for p in self._iter_log_paths():
                p.write_text(seed, encoding="utf-8")
        except Exception:
            # Logging should never break transport use
            pass

        # Snapshot machine state for the digital twin fallback
        try:
            import json as _json

            from science_jubilee._paths import machine_state_json

            _state = self._inner.get_machine_summary()
            _state_path = machine_state_json()
            _state_path.parent.mkdir(parents=True, exist_ok=True)
            _state_path.write_text(_json.dumps(_state, indent=2), encoding="utf-8")
        except Exception as _exc:
            import warnings

            warnings.warn(
                f"RecordingTransport: could not save machine_state.json: {_exc}"
            )

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
        """Return the test file stem from PYTEST_CURRENT_TEST if set."""
        val = os.getenv("PYTEST_CURRENT_TEST", "")
        return Path(val.split("::")[0]).stem if val else ""

    @staticmethod
    def _name_from_main() -> str:
        """Return the stem of __main__.__file__ for plain script execution."""
        main_file = getattr(sys.modules.get("__main__"), "__file__", None)
        return Path(main_file).stem if main_file else ""

    # Expose address if the inner transport has one
    @property
    def address(self) -> Optional[str]:
        return getattr(self._inner, "address", None)

    # ---- Macro resolution helpers --------------------------------------

    def _resolve_macro_path(self, rrf_path: str) -> Optional[Path]:
        """Resolve an RRF macro path to a local file, or None."""
        clean = rrf_path.strip().lstrip("/")
        if clean.startswith("macros/"):
            filename = clean[len("macros/") :]
            if self._macro_dir is not None:
                candidate = self._macro_dir / filename
                if candidate.exists():
                    return candidate
        # Look in sys_dir by bare filename
        bare = Path(clean).name
        if self._sys_dir is not None:
            candidate = self._sys_dir / bare
            if candidate.exists():
                return candidate
        # Fallback: macro_dir by bare filename
        if self._macro_dir is not None:
            candidate = self._macro_dir / bare
            if candidate.exists():
                return candidate
        return None

    def _read_gfile(self, path: Path) -> List[str]:
        """Read a .g file; skip blank lines and comments."""
        try:
            raw = path.read_text(encoding="utf-8").splitlines()
            result = []
            for line in raw:
                stripped = line.strip()
                if stripped and not stripped.startswith(";"):
                    result.append(stripped)
            return result
        except Exception:
            return []

    def _expand_lines(self, lines: List[str], depth: int = 0) -> List[str]:
        """Recursively expand M98 macro calls."""
        if depth >= _MAX_EXPAND_DEPTH:
            return lines
        result: List[str] = []
        for line in lines:
            m98 = re.match(r'^M98\s+P"([^"]+)"', line.strip())
            if m98:
                result.append(f"; {line.strip()}")
                macro_path = self._resolve_macro_path(m98.group(1))
                if macro_path:
                    inner = self._read_gfile(macro_path)
                    result.extend(self._expand_lines(inner, depth + 1))
                else:
                    result.append(f"; (macro not found: {m98.group(1)})")
            else:
                result.append(line)
        return result

    def _expand_cmd(self, cmd: str) -> List[str]:
        """Expand a single command into log lines (T{n} -> macro sequence, M98 -> file)."""
        stripped = cmd.strip()
        if not stripped:
            return []

        # Tool change: T{n} or T-1
        tool_match = re.match(r"^T(-?\d+)$", stripped)
        if tool_match:
            idx = int(tool_match.group(1))
            lines: List[str] = []
            try:
                cur = self._inner.get_active_tool_index()
            except Exception:
                cur = -1

            if idx >= 0:
                lines.append(f"; === tool change: T{idx} ===")
                # Free current tool first
                if cur >= 0:
                    tfree_path = self._resolve_macro_path(f"tfree{cur}.g")
                    if tfree_path:
                        lines.append(f"; tfree{cur}.g")
                        lines.extend(self._expand_lines(self._read_gfile(tfree_path)))
                    else:
                        lines.append(f"; (macro not found: tfree{cur}.g)")
                # Approach new tool
                tpre_path = self._resolve_macro_path(f"tpre{idx}.g")
                if tpre_path:
                    lines.append(f"; tpre{idx}.g")
                    lines.extend(self._expand_lines(self._read_gfile(tpre_path)))
                else:
                    lines.append(f"; (macro not found: tpre{idx}.g)")
                # Lock and restore
                tpost_path = self._resolve_macro_path(f"tpost{idx}.g")
                if tpost_path:
                    lines.append(f"; tpost{idx}.g")
                    lines.extend(self._expand_lines(self._read_gfile(tpost_path)))
                else:
                    lines.append(f"; (macro not found: tpost{idx}.g)")
            else:
                # T-1: park only
                lines.append("; === park tool: T-1 ===")
                if cur >= 0:
                    tfree_path = self._resolve_macro_path(f"tfree{cur}.g")
                    if tfree_path:
                        lines.append(f"; tfree{cur}.g")
                        lines.extend(self._expand_lines(self._read_gfile(tfree_path)))
                    else:
                        lines.append(f"; (macro not found: tfree{cur}.g)")

            lines.append(f"; {stripped}")
            return lines

        # Standalone M98 call
        m98_match = re.match(r'^M98\s+P"([^"]+)"', stripped)
        if m98_match:
            lines = [f"; {stripped}"]
            macro_path = self._resolve_macro_path(m98_match.group(1))
            if macro_path:
                inner = self._read_gfile(macro_path)
                lines.extend(self._expand_lines(inner))
            else:
                lines.append(f"; (macro not found: {m98_match.group(1)})")
            return lines

        return [stripped]

    def _log(self, cmd: str) -> None:
        try:
            if cmd is None:
                return
            lines = self._expand_cmd(str(cmd))
            if not lines:
                return
            text = "\n".join(lines) + "\n"
            for p in self._iter_log_paths():
                with p.open("a", encoding="utf-8") as f:
                    f.write(text)
        except Exception:
            pass

    # ---- Core transport methods ----------------------------------------
    def send_gcode(
        self,
        cmd: str = "",
        timeout: Optional[float] = None,
        response_wait: float = 60,
        wait: bool = False,
    ):
        # Record every command that goes through the transport
        self._log(cmd)
        return self._inner.send_gcode(
            cmd=cmd, timeout=timeout, response_wait=response_wait, wait=wait
        )

    def connect(self, timeout: Optional[float] = 5.0) -> bool:
        return self._inner.connect(timeout=timeout)

    def deck_is_clear(self) -> bool:
        return self._inner.deck_is_clear()

    # ---- Tools API ----------------------------------------------------
    def get_active_tool_index(self) -> int:
        return self._inner.get_active_tool_index()

    def select_tool(self, index: int) -> bool:
        # Route through send_gcode so the tool-change sequence is logged.
        try:
            self.send_gcode(f"T{int(index)}")
            return True
        except Exception:
            return False

    def park_tool(self) -> bool:
        try:
            self.send_gcode("T-1")
            return True
        except Exception:
            return False

    def get_tools(self) -> Dict[int, Dict[str, Any]]:
        return self._inner.get_tools()

    def get_tool_offsets(self) -> Dict[int, list[float]]:
        return self._inner.get_tool_offsets()

    def set_tool_offset(
        self,
        tool_idx: int,
        *,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> bool:
        # Log the equivalent G10 command, then delegate.
        parts = [f"P{int(tool_idx)}"]
        if x is not None:
            parts.append(f"X{float(x):.4f}")
        if y is not None:
            parts.append(f"Y{float(y):.4f}")
        if z is not None:
            parts.append(f"Z{float(z):.4f}")
        self._log("G10 " + " ".join(parts))
        return self._inner.set_tool_offset(tool_idx, x=x, y=y, z=z)

    def home_all(self) -> None:
        self.send_gcode('M98 P"homeall.g"', wait=True)

    def get_available_axes(self) -> list:
        return self._inner.get_available_axes()

    def get_axis_limits(self) -> dict:
        return self._inner.get_axis_limits()

    def get_positions(self) -> dict:
        return self._inner.get_positions()
