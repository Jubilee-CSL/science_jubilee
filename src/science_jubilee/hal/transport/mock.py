import json
from typing import Optional, Dict, List

from .base import BaseTransport


class MockTransport(BaseTransport):
    """Stateful mock transport that mirrors key HTTP responses for simulation and tests.
    deck_clear controls whether the deck is considered clear (True) or obstructed (False).
    """

    def __init__(self, deck_clear: bool = True):
        # Machine state
        self._deck_clear = deck_clear
        self.absolute_positioning = True
        self.absolute_extrusion = True
        self.position: Dict[str, float] = {"X": 0.0, "Y": 0.0, "Z": 0.0, "U": 0.0}
        self.axes_letters: List[str] = ["X", "Y", "Z", "U"]
        self.axis_limits: Dict[str, tuple] = {
            "X": (0.0, 300.0),
            "Y": (0.0, 300.0),
            "Z": (0.0, 200.0),
            "U": (0.0, 300.0),
        }
        self.axes_homed: List[bool] = [False, False, False, False]
        self.active_tool_index: int = -1
        # No tools configured by default
        self.tools: Dict[int, Dict] = {}

    def _reply(self, text: Optional[str]) -> Optional[str]:
        # For mock we simply return the text
        return text

    def _json(self, obj) -> str:
        return json.dumps({"result": obj})

    def send_gcode(self, cmd: str = "", timeout: Optional[float] = None, response_wait: float = 60, wait: bool = False):
        cmd = cmd.strip()
        # Positioning/extrusion modes
        if cmd == "G90":
            self.absolute_positioning = True
            return self._reply("ok")
        if cmd == "G91":
            self.absolute_positioning = False
            return self._reply("ok")
        if cmd == "M82":
            self.absolute_extrusion = True
            return self._reply("ok")
        if cmd == "M83":
            self.absolute_extrusion = False
            return self._reply("ok")

        # Homing
        if cmd.startswith("G28"):
            # Specific axes or all
            parts = cmd.split()
            if len(parts) == 1:
                # Home all
                self.axes_homed = [True] * len(self.axes_letters)
            else:
                for axis in [p for p in parts[1:] if p in self.axes_letters]:
                    idx = self.axes_letters.index(axis)
                    self.axes_homed[idx] = True
            return self._reply("ok")

        # Set current location
        if cmd.startswith("G92"):
            parts = cmd.split()
            for token in parts[1:]:
                axis = token[0]
                val = float(token[1:])
                if axis in self.position:
                    self.position[axis] = val
            return self._reply("ok")

        # Moves
        if cmd.startswith("G0") or cmd.startswith("G1"):
            parts = cmd.split()
            deltas = {}
            for token in parts[1:]:
                if token[0] in self.position:
                    try:
                        deltas[token[0]] = float(token[1:])
                    except ValueError:
                        # Param or feedrate; ignore
                        pass
            for axis, val in deltas.items():
                if self.absolute_positioning:
                    self.position[axis] = val
                else:
                    self.position[axis] += val
            return self._reply("ok")

        # Tool select or query
        if cmd == "T":
            if self.active_tool_index < 0:
                return self._reply("No tool is selected.")
            else:
                return self._reply(f"Tool {self.active_tool_index} is selected.")
        if cmd.startswith("T"):
            try:
                tool_idx = int(cmd[1:])
            except ValueError:
                tool_idx = -1
            if tool_idx < 0:
                self.active_tool_index = -1
                return self._reply("No tool is selected.")
            else:
                self.active_tool_index = tool_idx
                return self._reply(f"Tool {tool_idx} is selected.")

        # Position query
        if cmd == "M114":
            # Include 'Count' to match consumer expectations
            x = self.position.get("X", 0.0)
            y = self.position.get("Y", 0.0)
            z = self.position.get("Z", 0.0)
            u = self.position.get("U", 0.0)
            return self._reply(f"X:{x} Y:{y} Z:{z} U:{u} Count 0")

        # Object model queries used by Machine
        if cmd.startswith("M409"):
            # Extract key inside quotes e.g. M409 K"move.axes[].homed"
            key_start = cmd.find('K"')
            key_end = cmd.rfind('"')
            obj_key = cmd[key_start + 2:key_end] if key_start != -1 and key_end != -1 else ""

            if obj_key == "move.axes[]" or obj_key == "move.axes":
                # Return axis objects with letter/min/max/homed
                axes = []
                for i, letter in enumerate(self.axes_letters):
                    axes.append({
                        "letter": letter,
                        "min": self.axis_limits[letter][0],
                        "max": self.axis_limits[letter][1],
                        "homed": self.axes_homed[i],
                    })
                return self._json(axes)
            if obj_key == "move.axes[].homed":
                return self._json(self.axes_homed)
            if obj_key == "tools[]":
                # Minimal tools list with numbers and names
                tools = []
                for num, t in self.tools.items():
                    tools.append({"number": num, "name": t.get("name", f"tool{num}")})
                return self._json(tools)
            if obj_key == "tools":
                # Include offsets list; return empty by default
                tools = []
                for num, t in self.tools.items():
                    offsets = t.get("offsets", [0.0, 0.0, 0.0])
                    tools.append({"number": num, "offsets": offsets})
                return self._json(tools)

            # Default empty
            return self._json([])

        # Synchronize / dwell / reset etc.
        if cmd.startswith("M400"):
            return self._reply("ok")
        if cmd.startswith("G4"):
            return self._reply("ok")
        if cmd.startswith("M999"):
            # Reset mock state
            self.axes_homed = [False] * len(self.axes_letters)
            self.active_tool_index = -1
            return self._reply("ok")

        # Macros just return ok
        if cmd.startswith("M98"):
            return self._reply("ok")

        # Fallback
        return self._reply("")

    def connect(self, timeout: Optional[float] = 5.0) -> bool:
        """Mock transport is always reachable in simulation."""
        return True

    def deck_is_clear(self) -> bool:
        """Report deck clearance according to configured mock state.
        Future: compute based on world state (labware occupancy)."""
        return bool(self._deck_clear)

    # ---- Convenience: available axes (mock-specific) ---------------------
    def get_available_axes(self) -> list:
        """Return axis letters configured in the mock's world state.

        Provides a deterministic list used by simulation tests. Uppercases
        letters to match firmware convention.
        """
        return [str(x).upper() for x in self.axes_letters]

    def get_axis_limits(self) -> dict:
        """Return axis limits for the mock machine: letter -> (min, max)."""
        limits = {}
        for letter, (lo, hi) in self.axis_limits.items():
            limits[str(letter).upper()] = (float(lo), float(hi))
        return limits

    def get_positions(self) -> dict:
        """Return current axis positions from mock state."""
        return {str(k).upper(): float(v) for k, v in self.position.items()}

    # Use BaseTransport.format_machine_summary()

    # ---- Tools API (mock-specific) --------------------------------------
    def get_active_tool_index(self) -> int:
        return int(self.active_tool_index)

    def select_tool(self, index: int) -> bool:
        try:
            self.active_tool_index = int(index)
            # Ensure tool record exists
            if self.active_tool_index not in self.tools:
                self.tools[self.active_tool_index] = {"name": f"tool{self.active_tool_index}", "offsets": [0.0, 0.0, 0.0]}
            return True
        except Exception:
            return False

    def park_tool(self) -> bool:
        self.active_tool_index = -1
        return True

    def get_tools(self) -> dict:
        tools: Dict[int, Dict] = {}
        for num, t in self.tools.items():
            tools[int(num)] = {"name": t.get("name", f"tool{num}")}
        return tools

    def get_tool_offsets(self) -> dict:
        offsets: Dict[int, list[float]] = {}
        for num, t in self.tools.items():
            offs = t.get("offsets", [0.0, 0.0, 0.0])
            try:
                x, y, z = float(offs[0]), float(offs[1]), float(offs[2])
            except Exception:
                x, y, z = 0.0, 0.0, 0.0
            offsets[int(num)] = [x, y, z]
        return offsets

    def set_tool_offset(self, tool_idx: int, *, x: float | None = None, y: float | None = None, z: float | None = None) -> bool:
        try:
            rec = self.tools.get(int(tool_idx))
            if rec is None:
                rec = {"name": f"tool{int(tool_idx)}", "offsets": [0.0, 0.0, 0.0]}
                self.tools[int(tool_idx)] = rec
            offs = list(rec.get("offsets", [0.0, 0.0, 0.0]))
            if x is not None:
                offs[0] = float(x)
            if y is not None:
                offs[1] = float(y)
            if z is not None:
                offs[2] = float(z)
            rec["offsets"] = offs
            return True
        except Exception:
            return False
