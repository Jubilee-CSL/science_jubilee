from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.decks.Deck import Deck
from science_jubilee.labware.Labware import Labware, Well, Location


@dataclass
class DeckNavigator:
    """Coordinate motion across a deck and its labware using MotionDriver.

    This is a thin, high-level helper that:
    - uses Deck + Labware geometry to compute well coordinates
    - enforces safe Z travel based on Deck.safe_z
    - delegates all actual motion to a MotionDriver instance

    It does **not** talk to transports directly and does **not** know about
    tools; tools can call into it to move the machine control point.
    """

    driver: MotionDriver
    deck: Deck
    labware_by_slot: Mapping[int, Labware] = field(default_factory=dict)

    # --- basic helpers -------------------------------------------------
    def move_to_safe_z(self, margin: float = 20.0, speed: float = 6000.0) -> None:
        """Raise Z to a deck-safe height plus an optional extra margin.

        This mirrors the legacy Machine.safe_z_movement() logic but routes
        motion through MotionDriver and Deck.safe_z instead of talking to
        transports directly.
        """

        # Query current positions from the transport via MotionDriver
        pos = self.driver.transport.get_positions() or {}
        current_z = float(pos.get("Z", 0.0))
        safe_z = float(self.deck.safe_z)
        target = safe_z + float(margin)
        if current_z < target:
            self.driver.move_to({"Z": target}, s=speed, wait=True)

    # --- well targeting ------------------------------------------------
    def move_to_well(
        self,
        well: Well | Location,
        *,
        z_from_bottom: Optional[float] = None,
        z_from_top: Optional[float] = None,
        travel_margin: float = 20.0,
        speed_xy: float = 6000.0,
        speed_z: float = 3000.0,
    ) -> None:
        """Move to a single well in a collision-aware way.

        Parameters
        ----------
        well:
            Either a Well instance or a Location returned by Well.bottom()/top().
        z_from_bottom:
            If `well` is a Well, move to Well.bottom(z_from_bottom). Mutually
            exclusive with z_from_top. If both are None and well is a Well,
            the raw well.z is used (e.g., for just "above" the well).
        z_from_top:
            If `well` is a Well, move to Well.top(z_from_top). Mutually
            exclusive with z_from_bottom.
        travel_margin:
            Extra height (mm) above Deck.safe_z for XY travel.
        speed_xy:
            Feedrate for XY moves.
        speed_z:
            Feedrate for Z moves.
        """

        if isinstance(well, Location):
            x, y, z = well.point
        elif isinstance(well, Well):
            # Decide which Z helper to use
            if (z_from_bottom is not None) and (z_from_top is not None):
                raise ValueError("Specify at most one of z_from_bottom or z_from_top.")
            if z_from_bottom is not None:
                loc = well.bottom(float(z_from_bottom))
                x, y, z = loc.point
            elif z_from_top is not None:
                loc = well.top(float(z_from_top))
                x, y, z = loc.point
            else:
                # Raw well bottom plane, slightly above by default
                x, y, z = well.x, well.y, well.z
        else:
            raise TypeError(f"Unsupported well type: {type(well).__name__}")

        # 1) Go up to safe travel height
        self.move_to_safe_z(margin=travel_margin, speed=speed_z)

        # 2) XY move over the target well at safe Z
        self.driver.move_to({"X": float(x), "Y": float(y)}, s=speed_xy, wait=True)

        # 3) Move down in Z to target height
        self.driver.move_to({"Z": float(z)}, s=speed_z, wait=True)

    # --- iterating wells -----------------------------------------------
    def iter_wells(self, labware: Labware, order: str = "rows") -> Iterable[Well]:
        """Yield wells from a Labware in a specified logical order.

        Parameters
        ----------
        labware:
            The Labware whose wells to iterate.
        order:
            "rows" (default) or "columns". This is thin sugar around the
            structures already built inside Labware.
        """

        order = order.lower()
        if order not in {"rows", "columns"}:
            raise ValueError("order must be 'rows' or 'columns'")

        # Labware exposes row_data/column_data dicts of Row/Column objects.
        if order == "rows":
            for row in labware.row_data.values():
                for w in row.wells.values():
                    yield w
        else:  # columns
            for col in labware.column_data.values():
                for w in col.wells.values():
                    yield w

    # --- helpers by slot -----------------------------------------------
    def get_labware_in_slot(self, slot: int) -> Optional[Labware]:
        """Return Labware in the given deck slot, if any."""

        return self.labware_by_slot.get(int(slot))

    def iter_wells_in_slot(self, slot: int, order: str = "rows") -> Iterable[Well]:
        """Yield wells for the Labware loaded in a given deck slot.

        Raises
        ------
        KeyError if no labware is registered in that slot.
        """

        lw = self.get_labware_in_slot(slot)
        if lw is None:
            raise KeyError(f"No labware registered in slot {slot}.")
        return self.iter_wells(lw, order=order)
