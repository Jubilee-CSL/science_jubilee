import json
from typing import Optional, Any


class BaseTransport:
    """Abstract transport interface for gcode exchange."""

    def send_gcode(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False):
        """Send a G-Code command and return the response string or None.
        If wait is True, transports should block until motion completes (e.g., by issuing M400).
        Implementations should block until a response is available or timeout/response_wait is reached.
        """
        raise NotImplementedError()

    def connect(self, timeout: Optional[float] = 5.0) -> bool:
        """Establish or verify connectivity for the transport.
        Returns True if reachable/ready, False otherwise.
        Implementations may perform a lightweight ping.
        """
        raise NotImplementedError()

    def send_gcode_json(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False) -> Optional[Any]:
        """Send a G-Code command and parse a JSON response.
        Returns the parsed JSON object or None if parsing fails or no response.
        This does not interpret firmware-specific keys; it simply returns the decoded JSON.
        """
        resp = self.send_gcode(cmd=cmd, timeout=timeout, response_wait=response_wait, wait=wait)
        if resp is None:
            return None
        try:
            return json.loads(resp)
        except Exception:
            return None

    def deck_is_clear(self) -> bool:
        """Return True if the deck is clear of obstacles according to the transport's knowledge.
        Hardware transports may require an external provider or always return False.
        Mock/digital twin transports can compute this from world state.
        """
        raise NotImplementedError()

    # ---- Tools API (optional, but recommended) -------------------------
    def get_active_tool_index(self) -> int:
        """Return the currently selected tool index, or -1 if none.

        Implementations may query firmware state (e.g., via "T" or object model).
        Default implementation raises NotImplementedError.
        """
        raise NotImplementedError()

    def select_tool(self, index: int) -> bool:
        """Select tool by index using transport; return True on success."""
        raise NotImplementedError()

    def park_tool(self) -> bool:
        """Deselect any active tool (e.g., via T-1); return True on success."""
        raise NotImplementedError()

    def get_tools(self) -> dict:
        """Return tools configured on the machine.

        Structure: {number: {"name": str|None}}
        Implementations can add more keys (e.g., offsets).
        """
        raise NotImplementedError()

    def get_tool_offsets(self) -> dict:
        """Return tool offsets mapping number -> [X, Y, Z] floats if available."""
        raise NotImplementedError()

    def set_tool_offset(self, tool_idx: int, *, x: float | None = None, y: float | None = None, z: float | None = None) -> bool:
        """Set tool offset via G10 P{tool} X.. Y.. Z..; return True on success."""
        raise NotImplementedError()

    # ---- Convenience: homing state ---------------------------------------
    def get_axes_homed(self) -> list:
        """Return homed state for all axes as reported by the firmware object model.

        Uses M409 K"move.axes[].homed" via send_gcode_json(). Returns a list
        of booleans in firmware axis order, or an empty list if unavailable.
        """
        obj = self.send_gcode_json('M409 K"move.axes[].homed"')
        if obj and isinstance(obj, dict) and "result" in obj:
            return obj["result"]
        return []

    def is_homed_all(self) -> bool:
        """Return True if all reported axes are homed; False otherwise."""
        homed = self.get_axes_homed()
        return bool(homed) and all(homed)

    # ---- Convenience: available axes ------------------------------------
    def get_available_axes(self) -> list:
        """Return the list of available axis letters in firmware order.

        Transports vary in how they expose this information; implement
        in concrete transports (HTTPTransport, MockTransport) as needed.
        """
        raise NotImplementedError()

    # ---- Convenience: axis limits ---------------------------------------
    def get_axis_limits(self) -> dict:
        """Return a dict of axis limits mapping letter -> (min, max).

        Implement in concrete transports. Values should be floats.
        Example: {"X": (0.0, 300.0), "Y": (0.0, 300.0)}
        """
        raise NotImplementedError()

    # ---- Convenience: current positions --------------------------------
    def get_positions(self) -> dict:
        """Return the current axis positions mapping letter -> position.

        Implement in concrete transports (HTTPTransport, MockTransport).
        Values should be floats; letters uppercase.
        """
        raise NotImplementedError()

    # ---- Machine summary (dict) -----------------------------------------
    def get_machine_summary(self) -> dict:
        """Return a JSON-serializable dict summarizing machine state.

        Includes: transport, address, firmware, deck_clear, axes, homed,
        homed_map (when available), limits, positions, and tools info if available.
        """
        summary: dict[str, Any] = {
            "transport": self.__class__.__name__,
        }
        # Address/IP if available
        if hasattr(self, "address"):
            try:
                summary["address"] = getattr(self, "address")
            except Exception:
                summary["address"] = None

        # Firmware info via M115
        try:
            fw_resp = self.send_gcode("M115")
            summary["firmware"] = (fw_resp or "").strip()
        except Exception:
            summary["firmware"] = None

        # Deck clearance
        try:
            summary["deck_clear"] = bool(self.deck_is_clear())
        except Exception:
            summary["deck_clear"] = None

        # Axes
        try:
            letters = [str(x).upper() for x in (self.get_available_axes() or [])]
        except Exception:
            letters = []
        summary["axes"] = letters

        # Homed
        try:
            homed = self.get_axes_homed() or []
        except Exception:
            homed = []
        summary["homed"] = homed
        if letters and homed and len(letters) == len(homed):
            summary["homed_map"] = {l: bool(h) for l, h in zip(letters, homed)}
        else:
            summary["homed_map"] = {}

        # Limits
        try:
            limits = self.get_axis_limits() or {}
        except Exception:
            limits = {}
        summary["limits"] = limits

        # Positions
        try:
            positions = self.get_positions() or {}
        except Exception:
            positions = {}
        summary["positions"] = positions

        # Tools
        try:
            active_tool = self.get_active_tool_index()
        except Exception:
            active_tool = None
        summary["active_tool"] = active_tool
        try:
            tools = self.get_tools() or {}
        except Exception:
            tools = {}
        summary["tools"] = tools
        try:
            offsets = self.get_tool_offsets() or {}
        except Exception:
            offsets = {}
        summary["tool_offsets"] = offsets

        return summary

    # ---- Pretty summary (from dict) -------------------------------------
    def format_machine_summary(self) -> str:
        """Return a human-readable summary of machine state using dict summary."""
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
