
from __future__ import annotations
from enum import Enum
from typing import Union, Optional

class MotionDriver:
    """Thin motion layer for homing and movement.

    Public API is intentionally minimal:
    - home(axis)
    - move_to({axes: positions}, ...)
    - move({axes: deltas}, ...)
    - home_in_place(*axes)

    Safety gates (deck clearance) are enforced here; higher layers can add
    collision policies and axis-limit checks.
    """

    def __init__(self, transport):
        self.transport = transport
        # Cache of deck clearance status; None means unknown and will be asked
        # from the transport on demand.
        self._deck_clear_cached = None
        # Cache of available axis letters as reported by the current machine
        # state (transport or object model). None means not yet queried.
        self._axes_letters: Optional[list[str]] = None
        # Axis limits cache: letter -> (min, max)
        self._axis_limits: dict[str, tuple[float, float]] = {}
        # Initialize runtime Axis enum from current machine state
        self._init_runtime_axes()

    # ---- Axis definitions (runtime) --------------------------------------
    # Axis is created at runtime from the machine's available letters.
    Axis: Enum
    # Preferred axis ordering for coordinated moves; any remaining axes
    # not listed here will be appended in machine-reported order.
    PREFERRED_ORDER: list[str] = ["Z", "X", "Y", "U", "V", "E"]

    def _init_runtime_axes(self) -> None:
        # Fetch directly from transport to avoid driver-level fallbacks
        if not hasattr(self.transport, "get_available_axes"):
            raise NotImplementedError("Transport must implement get_available_axes() for Axis initialization.")
        try:
            letters_raw = self.transport.get_available_axes() or []
        except NotImplementedError:
            raise
        except Exception as e:
            raise NotImplementedError("Transport get_available_axes() failed during Axis initialization.") from e

        letters = [str(x).upper() for x in letters_raw]
        if not letters:
            raise NotImplementedError("Transport reported no available axes for Axis initialization.")

        # Dynamically construct the Axis enum based on machine truth
        MotionDriver.Axis = Enum("Axis", {l: l for l in letters})
        # Cache for later validations
        self._axes_letters = letters
        # Fetch and cache axis limits from transport if available
        if hasattr(self.transport, "get_axis_limits"):
            try:
                limits = self.transport.get_axis_limits() or {}
                # Normalize keys to uppercase and values to float tuples
                self._axis_limits = {
                    str(k).upper(): (float(v[0]), float(v[1]))
                    for k, v in limits.items()
                    if isinstance(v, (list, tuple)) and len(v) == 2
                }
            except Exception:
                self._axis_limits = {}

    # ---- G-code helpers ---------------------------------------------------
    def _gcode(self, cmd: str, wait: bool = False):
        """Internal: send a raw G-code command via the transport.

        MotionDriver's public API should remain high-level (home/move/etc.).
        This private helper provides the minimal bridge to transports that
        ultimately speak G-code.
        """
        # Prefer transport.send_gcode (HAL transports)
        if hasattr(self.transport, "send_gcode"):
            return self.transport.send_gcode(cmd=cmd, wait=wait)
        raise RuntimeError("Transport does not support gcode sending API.")

    def _set_absolute_positioning(self):
        """Ensure absolute positioning (G90)."""
        self._gcode("G90")

    def _set_relative_positioning(self):
        """Ensure relative positioning (G91)."""
        self._gcode("G91")

    # ---- Deck clearance caching ------------------------------------------
    def is_deck_clear(self) -> bool:
        """Return whether the deck is clear, using cached value if available.

        If unknown, asks the transport via deck_is_clear() and caches the
        result. Requires the transport to implement deck_is_clear().
        """
        if self._deck_clear_cached is not None:
            return self._deck_clear_cached
        if not hasattr(self.transport, "deck_is_clear"):
            raise RuntimeError("Transport must implement deck_is_clear() to allow homing.")
        clear = self.transport.deck_is_clear()
        self._deck_clear_cached = bool(clear)
        return self._deck_clear_cached

    def learn_deck_clearance(self, clear: bool) -> None:
        """Explicitly set the cached deck-clearance status."""
        self._deck_clear_cached = bool(clear)

    def invalidate_deck_clearance(self) -> None:
        """Forget cached deck-clearance status; next check will query transport."""
        self._deck_clear_cached = None

    # ---- Homing (clean, generic) -----------------------------------------
    def home_axis(self, axis):
        """Home a single axis.

        Homing Z requires deck clearance as reported by the transport, with
        lazy caching to avoid repeated prompts. Non-Z axes (e.g., X, Y, U)
        are homed without deck-clear gating to keep workflows non-interactive.
        """
        # Gate only Z homing behind deck-clear safety
        if axis.value == "Z":
            if not self.is_deck_clear():
                print("Deck is not clear. Aborting Z homing.")
                return

        self._gcode(f"G28 {axis.value}", wait=True)

    # ---- Motion (single-axis, absolute/relative) -------------------------
    def _normalize_axis(self, axis: Union[str, Enum]) -> Enum:
        """Normalize input to an Axis enum member and validate availability.

        Uses the transport-reported machine state to ensure the axis exists
        on the current machine. This prevents issuing commands for axes that
        are not configured.
        """
        if isinstance(axis, MotionDriver.Axis):
            # Validate availability against runtime machine axes
            letters = self._axes_letters or []
            if axis.value not in letters:
                raise ValueError(f"Axis '{axis.value}' is not available on this machine.")
            return axis
        if isinstance(axis, str):
            s = axis.strip().upper()
            if len(s) != 1:
                raise ValueError("Expected a single axis like 'x'.")
            try:
                member = MotionDriver.Axis[s]
                letters = self._axes_letters or []
                if s not in letters:
                    raise ValueError(f"Axis '{s}' is not available on this machine.")
                return member
            except KeyError:
                raise ValueError(f"Unknown axis '{axis}'.") from None
        raise TypeError(f"Unsupported axis type: {type(axis).__name__}")

    def move_to(
        self,
        axes: dict[Union[str, Enum], float],
        s: Optional[float] = 6000,
        param: Optional[str] = None,
        wait: bool = True,
    ) -> None:
        """Move multiple axes to absolute positions in a single coordinated line.

        Example: move_to({"x": 120.0, "y": 25.0}, s=6000)
        """
        self._move_compound(axes, absolute=True, s=s, param=param, wait=wait)

    def move(
        self,
        axes: dict[Union[str, Enum], float],
        s: Optional[float] = 6000,
        param: Optional[str] = None,
        wait: bool = True,
    ) -> None:
        """Move multiple axes relative to current positions in one line."""
        self._move_compound(axes, absolute=False, s=s, param=param, wait=wait)

    def _move_compound(
        self,
        axes: dict[Union[str, Enum], float],
        *,
        absolute: bool = True,
        s: Optional[float] = 6000,
        param: Optional[str] = None,
        wait: bool = True,
    ) -> None:
        """Issue a single G0 line moving multiple axes simultaneously.

        This preserves coordinated motion preferred by CNC controllers.
        Upper layers can prepare the axis map; MotionDriver validates, sets
        G90/G91, and formats the command.
        """
        if not axes:
            return

        # Set positioning mode
        if absolute:
            self._set_absolute_positioning()
        else:
            self._set_relative_positioning()

        # Normalize axis keys and build parts; prefer Z, then X,Y,U,V,E, then others
        normalized = {self._normalize_axis(k): v for k, v in axes.items()}

        # Gate motion behind deck-clear only if Z is being moved
        try:
            moving_z = any(ax.value == "Z" for ax in normalized.keys())
        except Exception:
            moving_z = False
        if moving_z and not self.is_deck_clear():
            print("Deck is not clear. Aborting Z motion.")
            return
        # Optional: validate requested targets against axis limits if known
        for ax, val in list(normalized.items()):
            lim = self._axis_limits.get(ax.value)
            if lim is not None:
                lo, hi = lim
                if not (lo <= float(val) <= hi):
                    raise ValueError(f"Requested {ax.value}={val} outside limits [{lo}, {hi}]")
        letters = self._axes_letters or []
        preferred = MotionDriver.PREFERRED_ORDER
        ordered_letters = [l for l in preferred if l in letters] + [l for l in letters if l not in preferred]
        parts = []
        for l in ordered_letters:
            # Only include axes present in this command
            if l in MotionDriver.Axis.__members__:
                ax = MotionDriver.Axis[l]
                if ax in normalized:
                    parts.append(f"{ax.value}{float(normalized[ax]):.2f}")
        if s is not None:
            parts.append(f"F{float(s):.2f}")
        if param:
            parts.append(param)

        self._gcode("G0 " + " ".join(parts), wait=wait)

    def home(self, axis: Union[str, Enum]):
        """Home a single axis, e.g., home('x') or home(MotionDriver.Axis.X).

        Keep it simple: accept exactly one axis. Orchestration can handle
        multi-axis homing if needed later.
        """
        axis_member = self._normalize_axis(axis)
        self.home_axis(axis_member)

    def home_in_place(self, *axes: Union[str, Enum]):
        """Set the current location of one or more axes to 0 using G92.

        Only a safe subset of axes is allowed (X, Y, Z, U). Provide axes
        as Axis enum members or strings.
        """
        allowed_letters = {"X", "Y", "Z", "U"}
        available = set(self._axes_letters or [])
        for axis in axes:
            axis_member = self._normalize_axis(axis)
            # Ensure axis is in the safe subset AND currently available
            if (axis_member.value not in allowed_letters) or (axis_member.value not in available):
                raise ValueError(f"Error: cannot home-in-place unknown/unsafe axis: {axis}.")
            self._gcode(f"G92 {axis_member.value}0")

    def get_axis_limits(self) -> dict[str, tuple[float, float]]:
        """Return cached axis limits mapping letter -> (min, max)."""
        return dict(self._axis_limits)

    # ---- Expose runtime axes to callers ---------------------------------
    def get_available_axes(self) -> list[str]:
        """Return the machine's available axes letters from MotionDriver's cache.

        If not yet initialized, this will call _init_runtime_axes() which
        consults the transport. No additional fallbacks are performed here.
        """
        if self._axes_letters is None:
            self._init_runtime_axes()
        return list(self._axes_letters or [])

    # ---- Tools convenience ----------------------------------------------
    def get_active_tool_index(self) -> int:
        """Return the currently selected tool index via transport, or -1."""
        if hasattr(self.transport, "get_active_tool_index"):
            try:
                return int(self.transport.get_active_tool_index())
            except Exception:
                return -1
        return -1

    def list_tools(self) -> dict:
        """Return a mapping of tool number -> info, when transport supports it."""
        if hasattr(self.transport, "get_tools"):
            try:
                return dict(self.transport.get_tools() or {})
            except Exception:
                return {}
        return {}

    def get_tool_offsets(self) -> dict:
        """Return tool offsets mapping number -> [X, Y, Z] when available."""
        if hasattr(self.transport, "get_tool_offsets"):
            try:
                return dict(self.transport.get_tool_offsets() or {})
            except Exception:
                return {}
        return {}

    def pickup_tool(self, index: int) -> bool:
        """Select a tool by index via the transport."""
        if not isinstance(index, int):
            raise TypeError("Tool index must be an integer.")
        if hasattr(self.transport, "select_tool"):
            try:
                return bool(self.transport.select_tool(index))
            except Exception:
                return False
        # Fallback: send raw gcode
        try:
            self._gcode(f"T{index}")
            return True
        except Exception:
            return False

    def park_tool(self) -> bool:
        """Deselect any active tool via the transport."""
        if hasattr(self.transport, "park_tool"):
            try:
                return bool(self.transport.park_tool())
            except Exception:
                return False
        try:
            self._gcode("T-1")
            return True
        except Exception:
            return False

    def set_tool_offset(self, tool_idx: int, *, x: float | None = None, y: float | None = None, z: float | None = None) -> bool:
        """Set tool offset (G10) via transport if available, else fallback to raw gcode."""
        if hasattr(self.transport, "set_tool_offset"):
            try:
                return bool(self.transport.set_tool_offset(tool_idx, x=x, y=y, z=z))
            except Exception:
                return False
        parts = [f"P{int(tool_idx)}"]
        if z is not None:
            parts.append(f"Z{float(z):.2f}")
        if x is not None:
            parts.append(f"X{float(x):.2f}")
        if y is not None:
            parts.append(f"Y{float(y):.2f}")
        try:
            self._gcode("G10 " + " ".join(parts))
            return True
        except Exception:
            return False

