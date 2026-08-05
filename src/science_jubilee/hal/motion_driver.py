from __future__ import annotations

import logging
from enum import Enum
from typing import Optional, Union

logger = logging.getLogger(__name__)


class MotionDriver:
    """Axis validation, safety gates, and move dispatch. Protocol-agnostic."""

    def __init__(self, transport):
        self.transport = transport
        self._deck_clear_cached = None
        self._axes_letters: Optional[list[str]] = None
        self._axis_limits: dict[str, tuple[float, float]] = {}
        self._axis: Optional[Enum] = None
        self._init_runtime_axes()

    def _init_runtime_axes(self) -> None:
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
        try:
            limits = self.transport.get_axis_limits() or {}
            self._axis_limits = {
                str(k).upper(): (float(v[0]), float(v[1]))
                for k, v in limits.items()
                if isinstance(v, (list, tuple)) and len(v) == 2
            }
        except Exception:
            self._axis_limits = {}

    def is_deck_clear(self) -> bool:
        """Return cached deck-clear status; queries transport on first call."""
        if self._deck_clear_cached is None:
            self._deck_clear_cached = bool(self.transport.deck_is_clear())
        return self._deck_clear_cached

    def learn_deck_clearance(self, clear: bool) -> None:
        self._deck_clear_cached = bool(clear)

    def invalidate_deck_clearance(self) -> None:
        self._deck_clear_cached = None

    def home_axis(self, axis) -> None:
        """Home a single axis. Z requires deck clearance."""
        if axis.value == "Z" and not self.is_deck_clear():
            logger.warning("Deck is not clear. Aborting Z homing.")
            return
        self.transport.home_axis(axis.value)

    def _normalize_axis(self, axis: Union[str, Enum]) -> Enum:
        """Validate and return an Axis enum member."""
        letters = self._axes_letters or []
        if isinstance(axis, self._axis):
            if axis.value not in letters:
                raise ValueError(f"Axis '{axis.value}' not available.")
            return axis
        if isinstance(axis, str):
            s = axis.strip().upper()
            if len(s) != 1:
                raise ValueError("Expected a single axis letter.")
            if s not in letters:
                raise ValueError(f"Axis '{s}' not available.")
            try:
                return self._axis[s]
            except KeyError:
                raise ValueError(f"Unknown axis '{axis}'.") from None
        raise TypeError(f"Unsupported axis type: {type(axis).__name__}")

    def move_to(
        self,
        axes: dict[Union[str, Enum], float],
        s: Optional[float] = 6000,
        wait: bool = True,
    ) -> None:
        """Move to absolute positions. Example: move_to({'X': 120, 'Y': 25})"""
        self._move_compound(axes, absolute=True, s=s, wait=wait)

    def move(
        self,
        axes: dict[Union[str, Enum], float],
        s: Optional[float] = 6000,
        wait: bool = True,
    ) -> None:
        """Move by relative deltas."""
        self._move_compound(axes, absolute=False, s=s, wait=wait)

    def _move_compound(
        self,
        axes: dict[Union[str, Enum], float],
        *,
        absolute: bool = True,
        s: Optional[float] = 6000,
        wait: bool = True,
    ) -> None:
        if not axes:
            return
        normalized = {self._normalize_axis(k): v for k, v in axes.items()}
        if any(ax.value == "Z" for ax in normalized) and not self.is_deck_clear():
            logger.warning("Deck is not clear. Aborting Z motion.")
            return
        if not absolute:
            current = self.get_positions()
        for ax, val in normalized.items():
            lim = self._axis_limits.get(ax.value)
            if lim is not None:
                lo, hi = lim
                check = float(val) if absolute else current.get(ax.value, 0.0) + float(val)
                if not (lo <= check <= hi):
                    raise ValueError(f"{ax.value}={check} outside limits [{lo}, {hi}]")
        self.transport.move_axes(
            {ax.value: float(v) for ax, v in normalized.items()},
            feedrate=s,
            absolute=absolute,
            wait=wait,
        )
        self.invalidate_deck_clearance()

    def home(self, axis: Union[str, Enum]) -> None:
        """Home a single axis by letter or enum member."""
        self.home_axis(self._normalize_axis(axis))

    def home_in_place(self, *axes: Union[str, Enum]) -> None:
        """Zero one or more axes in place (G92). Only X/Y/Z/U allowed."""
        allowed = {"X", "Y", "Z", "U"}
        available = set(self._axes_letters or [])
        for axis in axes:
            member = self._normalize_axis(axis)
            if member.value not in allowed or member.value not in available:
                raise ValueError(f"Cannot home-in-place axis: {axis}.")
            self.transport.home_in_place(member.value)

    def get_positions(self) -> dict[str, float]:
        return self.transport.get_positions() or {}

    def get_available_axes(self) -> list[str]:
        return list(self._axes_letters or [])

    def get_axis_limits(self) -> dict[str, tuple[float, float]]:
        return dict(self._axis_limits)

    def home_all(self) -> None:
        """Home all axes. Requires deck clearance."""
        if not self.is_deck_clear():
            logger.warning("Deck is not clear. Aborting home_all.")
            return
        self.transport.home_all()
        self.invalidate_deck_clearance()

    def get_axes_homed(self) -> list:
        return self.transport.get_axes_homed()
