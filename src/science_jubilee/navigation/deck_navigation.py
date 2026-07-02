from __future__ import annotations

from typing import Iterable

from dataclasses import dataclass


from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.decks.Deck import Deck
from science_jubilee.labware.Labware import (
    Labware,
    Location,Point,
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

    def move_to_safe_z(self,margin: float | None = None,speed: float | None = None,) -> None:
        """
        Raise the machine to a safe travel height.
        """
        margin = (self.travel_margin if margin is None else margin)
        speed = (self.default_speed_z if speed is None else speed)

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
    def move_to_well(self,
        well: Well,
        speed_xy: float | None = None,
        speed_z: float | None = None,
        margin: float = None) -> None:
        """
        Collision-safe movement toward a Well or Location.
        """

        speed_xy = (self.default_speed_xy if speed_xy is None else speed_xy)
        speed_z = (self.default_speed_z if speed_z is None else speed_z)
        margin = (self.travel_margin if margin is None else margin)


        # 1) Move to safe travel Z, if safe_movement is true
        self.move_to_safe_z(margin=margin,speed=speed_z,)

        # 2) XY trave
        self.driver.move_to({"X": float(well.x),"Y": float(well.y),"Z": float(well.top)},s=speed_xy,wait=True)


    def move_to_water_level(self, well: Well,surface: bool = False,speed_z: float | None = None,):

        speed_z = (self.default_speed_z if speed_z is None else speed_z)

        position = self.driver.get_positions
        if not well.in_usable_space(Location
                                    (point = Point(position["X"],
                                                   position["Y"],
                                                   position["Z"]))):
            
            raise ValueError("Need to be inside a well to use this fonctions")
        
        #A modifié si une méthode efficace existe pour ce déplacer vers la surface de l'eau d'un puit
        if surface == True:
            self.driver.move_to({"Z":float(well.depth)},s=speed_z,wait=True)
        else:
            self.driver.move_to({"Z":float(well.bottom)},s=speed_z,wait=True)



    def xy_move_inside_well(self, well:Well, x:float, y:float,speed_xy:float |None = None,random:bool = False):
        
        speed_xy = (self.default_speed_xy if speed_xy is None else speed_xy)

        if random:
            destination : Location = well.random_point()
        else:
            destination : Location = well.safe_move(well,x,y)
        self.driver.move_to({"X":float(destination.point.x),
                             "Y":float(destination.point.y)},
                             s=speed_xy,wait=True)
    
    # ------------------------------------------------------------------
    # Deck helpers
    # ------------------------------------------------------------------
    def get_labware_in_slot(self,slot_id: str | int) -> Labware:
        """
        Retrieve loaded labware from deck.
        """
        slot = self.deck.get_slot(str(slot_id))

        return slot.get_labware()

    def get_well(self,slot_id: str | int,well_id: str,) -> Well:
        """
        Retrieve a well directly from deck state.
        """

        return self.deck.get_well(str(slot_id),well_id)
    
    