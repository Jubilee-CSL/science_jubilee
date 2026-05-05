
from __future__ import annotations
from enum import Enum
from typing import Union, Optional

class MotionDriver:
    """Thin motion layer: G-code formatting, axis validation, and safety gates.

    Public API:
    - home(axis)
    - move_to({axes: positions}, ...)
    - move({axes: deltas}, ...)
    - home_in_place(*axes)
    - get_positions() -> dict[str, float]
    - get_available_axes() -> list[str]
    - get_axis_limits() -> dict[str, tuple[float, float]]

    Does NOT manage tools. Tool pickup/park/offset belongs in a higher layer.
    """

    # Preferred axis ordering for coordinated moves.
    _PREFERRED_ORDER: list[str] = ["Z", "X", "Y", "U", "V", "E"]

    def __init__(self, transport):
        self.transport = transport
        self._deck_clear_cached = None
        self._axes_letters: Optional[list[str]] = None
        self._axis_limits: dict[str, tuple[float, float]] = {}
        # Per-instance Axis enum built from machine state
        self._axis: Optional[Enum] = None
        self._init_runtime_axes()

    # ---- Axis definitions (runtime, per-instance) ------------------------
    def _init_runtime_axes(self) -> None:
        if not hasattr(self.transport, "get_available_axes"):
            raise NotImplementedError("Transport must implement get_available_axes().")
        try:
            letters_raw = self.transport.get_available_axes() or []
        except NotImplementedError:
            raise
        except Exception as e:
            raise NotImplementedError("Transport get_available_axes() failed.") from e

        letters = [str(x).upper() for x in letters_raw]
        if not letters:
            raise NotImplementedError("Transport reported no available axes.")

        self._axis = Enum("Axis", {l: l for l in letters})
        self._axes_letters = letters

        if hasattr(self.transport, "get_axis_limits"):
            try:
                limits = self.transport.get_axis_limits() or {}
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

        self.transport.home_axis(axis.value)


    # ---- Motion (single-axis, absolute/relative) -------------------------
    def _normalize_axis(self, axis: Union[str, Enum]) -> Enum:
        """Normalize a string or Axis enum member; validate it is available."""
        letters = self._axes_letters or []
        if isinstance(axis, self._axis):
            if axis.value not in letters:
                raise ValueError(f"Axis '{axis.value}' is not available on this machine.")
            return axis
        if isinstance(axis, str):
            s = axis.strip().upper()
            if len(s) != 1:
                raise ValueError("Expected a single axis letter like 'X'.")
            if s not in letters:
                raise ValueError(f"Axis '{s}' is not available on this machine.")
            try:
                return self._axis[s]
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
        preferred = self._PREFERRED_ORDER
        ordered_letters = [l for l in preferred if l in letters] + [l for l in letters if l not in preferred]
        parts = []
        for l in ordered_letters:
            if l in self._axis.__members__:
                ax = self._axis[l]
                if ax in normalized:
                    parts.append(f"{ax.value}{float(normalized[ax]):.2f}")
        if s is not None:
            parts.append(f"F{float(s):.2f}")
        if param:
            parts.append(param)

        self._gcode("G0 " + " ".join(parts), wait=wait)

    def home(self, axis: Union[str, Enum]):
        """Home a single axis, e.g., home('X') or home(driver._axis.X)."""
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
            self.transport.home_in_place(axis_member.value)

    # ---- Queries forwarded from transport --------------------------------
    def get_positions(self) -> dict[str, float]:
        """Return current axis positions mapping letter -> float."""
        return self.transport.get_positions() or {}

    def get_available_axes(self) -> list[str]:
        """Return cached available axis letters."""
        return list(self._axes_letters or [])

    def get_axis_limits(self) -> dict[str, tuple[float, float]]:
        """Return cached axis limits mapping letter -> (min, max)."""
        return dict(self._axis_limits)

