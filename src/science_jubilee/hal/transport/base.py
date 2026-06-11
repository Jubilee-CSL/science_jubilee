import json
from abc import ABC, abstractmethod
from typing import Optional, Any


class BaseTransport(ABC):
    """Abstract base for all G-code transports (HTTP, serial, mock, ...).

    Subclasses implement delivery; this class owns G-code construction.
    Higher layers never build G-code strings.
    """

    @abstractmethod
    def send_gcode(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False) -> Optional[str]:
        """Send a G-code command; return response string or None."""

    @abstractmethod
    def connect(self, timeout: Optional[float] = 5.0) -> bool:
        """Return True if the machine is reachable."""

    @abstractmethod
    def deck_is_clear(self) -> bool:
        """Return True if the deck is clear of obstacles."""

    @abstractmethod
    def get_available_axes(self) -> list:
        """Return axis letters in firmware order (uppercase)."""

    @abstractmethod
    def get_axis_limits(self) -> dict:
        """Return axis limits: letter -> (min, max)."""

    @abstractmethod
    def get_positions(self) -> dict:
        """Return current positions: letter -> float."""

    def move_axes(
        self,
        axes: dict[str, float],
        feedrate: Optional[float] = None,
        *,
        absolute: bool = True,
        wait: bool = True,
    ) -> None:
        """Set positioning mode (G90/G91) then issue G0."""
        self.send_gcode("G90" if absolute else "G91")
        parts = [f"{ax}{float(val):.4f}" for ax, val in axes.items()]
        if feedrate is not None:
            parts.append(f"F{float(feedrate):.2f}")
        self.send_gcode("G0 " + " ".join(parts), wait=wait)

    def send_gcode_json(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False) -> Optional[Any]:
        """Send a G-code command and return the parsed JSON response, or None."""
        resp = self.send_gcode(cmd=cmd, timeout=timeout, response_wait=response_wait, wait=wait)
        if resp is None:
            return None
        try:
            return json.loads(resp)
        except Exception:
            return None

    # ---- Tools API -------------------------------------------------------
    def get_active_tool_index(self) -> int:
        """Return the active tool index, or -1 if none."""
        raise NotImplementedError()

    def select_tool(self, tool_idx: int) -> bool:
        raise NotImplementedError()

    def park_tool(self) -> bool:
        raise NotImplementedError()

    def get_tools(self) -> dict:
        """Return {number: {"name": str}} for configured tools."""
        raise NotImplementedError()

    def get_tool_offsets(self) -> dict:
        """Return {number: [X, Y, Z]} offsets for all tools."""
        raise NotImplementedError()

    # ---- Homing ----------------------------------------------------------
    def get_axes_homed(self) -> list:
        """Return list of homed booleans in firmware axis order."""
        obj = self.send_gcode_json('M409 K"move.axes[].homed"')
        if obj and isinstance(obj, dict) and "result" in obj:
            return obj["result"]
        return []

    def is_homed_all(self) -> bool:
        homed = self.get_axes_homed()
        return bool(homed) and all(homed)

    def home_all(self) -> None:
        self.send_gcode('M98 P"homeall.g"', wait=True)

    def home_axis(self, letter: str) -> None:
        self.send_gcode(f"G28 {letter.upper()}", wait=True)

    def home_in_place(self, letter: str) -> None:
        self.send_gcode(f"G92 {letter.upper()}0")

    def tool_lock(self) -> None:
        self.send_gcode('M98 P"/macros/tool_lock.g"', wait=True)

    def tool_unlock(self) -> None:
        self.send_gcode('M98 P"/macros/tool_unlock.g"', wait=True)

    # ---- Machine summary -------------------------------------------------
    def get_machine_summary(self) -> dict:
        """Return a dict of current machine state."""
        summary: dict[str, Any] = {"transport": self.__class__.__name__}
        if hasattr(self, "address"):
            summary["address"] = getattr(self, "address", None)
        try:
            summary["firmware"] = (self.send_gcode("M115") or "").strip()
        except Exception:
            summary["firmware"] = None
        try:
            summary["deck_clear"] = bool(self.deck_is_clear())
        except Exception:
            summary["deck_clear"] = None
        try:
            letters = [str(x).upper() for x in (self.get_available_axes() or [])]
        except Exception:
            letters = []
        summary["axes"] = letters
        try:
            homed = self.get_axes_homed() or []
        except Exception:
            homed = []
        summary["homed"] = homed
        summary["homed_map"] = {l: bool(h) for l, h in zip(letters, homed)} if len(letters) == len(homed) else {}
        try:
            summary["limits"] = self.get_axis_limits() or {}
        except Exception:
            summary["limits"] = {}
        try:
            summary["positions"] = self.get_positions() or {}
        except Exception:
            summary["positions"] = {}
        try:
            summary["active_tool"] = self.get_active_tool_index()
        except Exception:
            summary["active_tool"] = None
        try:
            summary["tools"] = self.get_tools() or {}
        except Exception:
            summary["tools"] = {}
        try:
            summary["tool_offsets"] = self.get_tool_offsets() or {}
        except Exception:
            summary["tool_offsets"] = {}
        return summary

    def format_machine_summary(self) -> str:
        """Return a human-readable summary string."""
        s = self.get_machine_summary()
        lines: list[str] = []
        lines.append(f"Transport: {s.get('transport')}")
        addr = s.get("address")
        if addr:
            lines.append(f"Address: {addr}")
        fw = s.get("firmware")
        lines.append(f"Firmware: {fw[:120]}" if isinstance(fw, str) and fw else "Firmware: (unavailable)")
        dc = s.get("deck_clear")
        if dc is not None:
            lines.append(f"Deck clear: {bool(dc)}")
        letters = s.get("axes") or []
        lines.append(f"Axes: {' '.join(letters) if letters else '(unknown)'}")
        homed_map = s.get("homed_map") or {}
        limits = s.get("limits") or {}
        positions = s.get("positions") or {}

        lines.append("Limits & state:")
        seq = letters if letters else list(limits.keys() or positions.keys())
        for l in seq:
            rng = limits.get(l)
            pos = positions.get(l)
            h = homed_map.get(l)
            rng_txt = f"[{rng[0]}, {rng[1]}]" if rng else "(no limits)"
            pos_txt = f"{pos:.3f}" if isinstance(pos, (int, float)) else "(unknown)"
            hm_txt = f" homed={h}" if l in homed_map else ""
            lines.append(f"  {l}: {rng_txt} pos={pos_txt}{hm_txt}")

        return "\n".join(lines)
