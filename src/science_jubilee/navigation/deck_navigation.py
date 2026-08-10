from __future__ import annotations

import logging
from dataclasses import dataclass

from science_jubilee.decks.Deck import Deck
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.labware.Labware import Labware, Location, Point, Well

logger = logging.getLogger(__name__)


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
        margin = self.travel_margin if margin is None else margin
        speed = self.default_speed_z if speed is None else speed

        current_position = self.driver.get_positions()
        current_z = float(current_position.get("Z", 0.0))
        target_z = float(self.deck.safe_z) + float(margin)

        if current_z < target_z:
            self.driver.move_to(
                {"Z": target_z},
                s=speed,
                wait=True,
            )

    # ------------------------------------------------------------------
    # Well movement
    # ------------------------------------------------------------------
    def move_to_well(
        self,
        well: Well,
        speed_xy: float | None = None,
        speed_z: float | None = None,
        margin: float = None,
    ) -> None:
        """
        Collision-safe movement toward a Well or Location.
        """

        speed_xy = self.default_speed_xy if speed_xy is None else speed_xy
        speed_z = self.default_speed_z if speed_z is None else speed_z
        margin = self.travel_margin if margin is None else margin

        # 1) Move to safe travel Z, if safe_movement is true
        self.move_to_safe_z(
            margin=margin,
            speed=speed_z,
        )

        # 2) XY trave
        self.driver.move_to({"X": float(well.x)}, s=speed_xy, wait=True)
        self.driver.move_to({"Y": float(well.y)}, s=speed_xy, wait=True)

        # 2) Z travel
        self.driver.move_to({"Z": float(well.top)}, s=speed_z, wait=True)

    def move_inside_well(
        self,
        well: Well,
        dx: float = 0,
        dy: float = 0,
        dz: float = 0,
        z: float | None = None,
        speed_xy: float | None = None,
        speed_z: float | None = None,
    ):

        speed_xy = self.default_speed_xy if speed_xy is None else speed_xy
        speed_z = self.default_speed_z if speed_z is None else speed_z

        position = self.driver.get_positions()
        location = Location(
            point=Point(x=position["X"], y=position["Y"], z=position["Z"]),
            resource=well,
        )

        if (dx or dy) != 0:
            destination: Location = well.safe_move(location, dx, dy)
            self.driver.move_to(
                {"X": float(destination.point.x)}, s=speed_xy, wait=True
            )
            self.driver.move_to(
                {"Y": float(destination.point.y)}, s=speed_xy, wait=True
            )

        if z is not None:
            self.driver.move_to({"Z": float(z)}, s=speed_z, wait=True)
        elif dz != 0:
            self.driver.move_to(
                {"Z": float(location.point.z + dz)}, s=speed_z, wait=True
            )

    def random_move_inside_well(
        self, well: Well, margin: float = 0.6, speed_xy: float | None = None
    ):

        destination = well.random_point(safety_margin=margin)
        logger.info(destination)
        self.move_inside_well(
            well, destination.point.x, destination.point.y, speed_xy=speed_xy
        )

    # ------------------------------------------------------------------
    # Deck helpers
    # ------------------------------------------------------------------
    def get_labware_in_slot(self, slot_id: str | int) -> Labware:
        """
        Retrieve loaded labware from deck.
        """
        slot = self.deck.get_slot(str(slot_id))

        return slot.get_labware()

    def get_well(
        self,
        slot_id: str | int,
        well_id: str,
    ) -> Well:
        """
        Retrieve a well directly from deck state.
        """

        return self.deck.get_well(str(slot_id), well_id)

    def get_wells_in_slot(self, slot_id: str | int) -> list[Well]:
        """
        Retrieve loaded labware from deck.
        """
        labware = self.get_labware_in_slot(slot_id)

        return labware.get_wells()
