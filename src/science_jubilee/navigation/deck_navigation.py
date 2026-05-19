from __future__ import annotations

from typing import Iterable

from dataclasses import dataclass


from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.decks.Deck import Deck
from science_jubilee.labware.Labware import (
    Labware,
    Location,
    Well,
)


@dataclass(slots=True)
class DeckNavigator:
    """
    High-level navigation helper using Deck + Labware geometry.

    Responsibilities:
    - compute motion targets from runtime geometry
    - enforce safe Z travel
    - delegate physical movement to MotionDriver

    This class contains NO motion planning logic.
    """

    driver: MotionDriver

    deck: Deck

    travel_margin: float = 20.0

    default_speed_xy: float = 6000.0

    default_speed_z: float = 3000.0

    # ------------------------------------------------------------------
    # Safe Z movement
    # ------------------------------------------------------------------

    def move_to_safe_z(
        self,
        margin: float | None = None,
        speed: float | None = None,
    ) -> None:
        """
        Raise the machine to a safe travel height.
        """

        margin = (
            self.travel_margin
            if margin is None
            else margin
        )

        speed = (
            self.default_speed_z
            if speed is None
            else speed
        )

        current_position = self.driver.get_positions()

        current_z = float(current_position.get("Z", 0.0))

        target_z = (float(self.deck.safe_z)+ float(margin))

        if current_z < target_z:

            self.driver.move_to(
                {"Z": target_z},
                s=speed,
                wait=True,
            )

    # ------------------------------------------------------------------
    # Well movement
    # ------------------------------------------------------------------

    #move safely to well only, ajouter une option not safe ?
    def move_to_target(
        self,
        target: Well | Location,
        *,
        z_from_bottom: float | None = None,
        z_from_top: float | None = None,
        speed_xy: float | None = None,
        speed_z: float | None = None,
        travel_margin: float | None = None,
        safe_movemet: bool = True
    ) -> None:
        """
        Collision-safe movement toward a Well or Location.
        """

        speed_xy = (
            self.default_speed_xy
            if speed_xy is None
            else speed_xy
        )

        speed_z = (
            self.default_speed_z
            if speed_z is None
            else speed_z
        )

        x, y, z = self._resolve_target_position(
            target=target,
            z_from_bottom=z_from_bottom,
            z_from_top=z_from_top,
        )

        # 1) Move to safe travel Z, if safe_movement is true
        if safe_movemet == True:
            self.move_to_safe_z(margin=travel_margin,speed=speed_z,)

        # 2) XY travel

        self.driver.move_to(
            {
                "X": float(x),
                "Y": float(y),
            },
            s=speed_xy,
            wait=True,
        )

        # 3) Descend in Z

        self.driver.move_to(
            {
                "Z": float(z),
            },
            s=speed_z,
            wait=True,
        )

    # ------------------------------------------------------------------
    # Target resolution
    # ------------------------------------------------------------------

    def _resolve_target_position(
        self,
        *,
        target: Well | Location,
        z_from_bottom: float | None,
        z_from_top: float | None,
    ) -> tuple[float, float, float]:
        """
        Resolve runtime coordinates from Well or Location.
        """

        if (
            z_from_bottom is not None
            and z_from_top is not None
        ):
            raise ValueError(
                "Specify only one of "
                "z_from_bottom or z_from_top."
            )

        # --------------------------------------------------------------
        # Direct location
        # --------------------------------------------------------------

        if isinstance(target, Location):

            return (target.point.x,target.point.y,target.point.z,)

        # --------------------------------------------------------------
        # Well target
        # --------------------------------------------------------------

        if isinstance(target, Well):

            if z_from_bottom is not None:

                location = target.get_bottom_location(
                    z_from_bottom
                )

                return (location.point.x,location.point.y,location.point.z)

            if z_from_top is not None:

                location = target.get_top_location(z_from_top)

                return (location.point.x,location.point.y,location.point.z)


            return (target.x,target.y,target.z)

        raise TypeError(
            f"Unsupported target type: "
            f"{type(target).__name__}"
        )

    # ------------------------------------------------------------------
    # Deck helpers
    # ------------------------------------------------------------------

    def get_labware_in_slot(
        self,
        slot_id: str | int,
    ) -> Labware:
        """
        Retrieve loaded labware from deck.
        """

        slot = self.deck.get_slot(
            str(slot_id)
        )

        return slot.get_labware()

    def get_well(
        self,
        slot_id: str | int,
        well_id: str,
    ) -> Well:
        """
        Retrieve a well directly from deck state.
        """

        return self.deck.get_well(
            str(slot_id),
            well_id,
        )