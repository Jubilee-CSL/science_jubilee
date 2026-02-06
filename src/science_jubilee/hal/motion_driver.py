
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

    # ---- Axis definitions -------------------------------------------------
    class Axis(Enum):
        X = "X"
        Y = "Y"
        Z = "Z"
        U = "U"  # Tool changer/carriage
        V = "V"  # Auxiliary axis (if present)
        E = "E"  # Extruder/syringe

    # Subset of axes that are safe to home/set in place via G92
    _G92_ALLOWED: set["MotionDriver.Axis"] = {Axis.X, Axis.Y, Axis.Z, Axis.U}

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
        # Fallbacks for legacy transports
        if hasattr(self.transport, "gcode"):
            return self.transport.gcode(cmd, wait=wait)
        if hasattr(self.transport, "send_command"):
            return self.transport.send_command("gcode", {"cmd": cmd, "wait": wait})
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
    def home_axis(self, axis: "MotionDriver.Axis"):
        """Home a single axis.

        All axis homing requires deck clearance as reported by the transport,
        with lazy caching to avoid repeated prompts.
        """
        # Check clearance (cached or ask transport)
        if not self.is_deck_clear():
            print("Deck is not clear. Aborting axis homing.")
            return
        
        self._gcode(f"G28 {axis.value}", wait=True)

    # ---- Motion (single-axis, absolute/relative) -------------------------
    def _normalize_axis(self, axis: Union[str, "MotionDriver.Axis"]) -> "MotionDriver.Axis":
        """Normalize input to an Axis enum member."""
        if isinstance(axis, MotionDriver.Axis):
            return axis
        if isinstance(axis, str):
            s = axis.strip().upper()
            if len(s) != 1:
                raise ValueError("Expected a single axis like 'x'.")
            try:
                return MotionDriver.Axis[s]
            except KeyError:
                raise ValueError(f"Unknown axis '{axis}'.") from None
        raise TypeError(f"Unsupported axis type: {type(axis).__name__}")

    def move_to(
        self,
        axes: dict[Union[str, "MotionDriver.Axis"], float],
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
        axes: dict[Union[str, "MotionDriver.Axis"], float],
        s: Optional[float] = 6000,
        param: Optional[str] = None,
        wait: bool = True,
    ) -> None:
        """Move multiple axes relative to current positions in one line."""
        self._move_compound(axes, absolute=False, s=s, param=param, wait=wait)

    def _move_compound(
        self,
        axes: dict[Union[str, "MotionDriver.Axis"], float],
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
        if not self.is_deck_clear():
            print("Deck is not clear. Aborting motion.")
            return

        # Set positioning mode
        if absolute:
            self._set_absolute_positioning()
        else:
            self._set_relative_positioning()

        # Normalize axis keys and build parts; prefer Z first, then X,Y,U,V,E
        normalized = {self._normalize_axis(k): v for k, v in axes.items()}
        order = [MotionDriver.Axis.Z, MotionDriver.Axis.X, MotionDriver.Axis.Y,
                 MotionDriver.Axis.U, MotionDriver.Axis.V, MotionDriver.Axis.E]
        parts = []
        for ax in order:
            if ax in normalized:
                parts.append(f"{ax.value}{float(normalized[ax]):.2f}")
        if s is not None:
            parts.append(f"F{float(s):.2f}")
        if param:
            parts.append(param)

        self._gcode("G0 " + " ".join(parts), wait=wait)

    def home(self, axis: Union[str, "MotionDriver.Axis"]):
        """Home a single axis, e.g., home('x') or home(MotionDriver.Axis.X).

        Keep it simple: accept exactly one axis. Orchestration can handle
        multi-axis homing if needed later.
        """
        axis_member = self._normalize_axis(axis)
        self.home_axis(axis_member)

    def home_in_place(self, *axes: Union[str, "MotionDriver.Axis"]):
        """Set the current location of one or more axes to 0 using G92.

        Only a safe subset of axes is allowed (X, Y, Z, U). Provide axes
        as Axis enum members or strings.
        """
        for axis in axes:
            axis_member = self._normalize_axis(axis)
            if axis_member not in self._G92_ALLOWED:
                raise ValueError(f"Error: cannot home-in-place unknown/unsafe axis: {axis}.")
            self._gcode(f"G92 {axis_member.value}0")