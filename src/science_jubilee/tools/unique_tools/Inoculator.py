from science_jubilee.labware.Labware import (Location,Point,Well)
from dataclasses import dataclass

from science_jubilee.navigation.deck_navigation import DeckNavigator
from science_jubilee.tools.tool import Tool, requires_active_tool


@dataclass(slots=True, repr=False)
class Inoculator(Tool):
    """A class representation of an inoculator.

    :param Tool: The base tool class
    :type Tool: :class:`Tool`
    """
    
    @requires_active_tool
    def transfer(self,nav: DeckNavigator, source: Well, destination: list[Well],
        *,
        speed_xy: float = 8000,
        sweep_x: float = 5.0, sweep_y: float = 5.0, sweep_speed: float = 500.0,
        randomize_pickup: bool = False,
    ) -> None:
        """
        Transfer an object from source well to destination well.
        """
        
        for well_dest in destination:
            nav.move_to_well(source,speed_xy,margin=10)

            if randomize_pickup:
                pickup_position = source.random_point(source.depth, safety_margin= 0.8)
                nav.move_inside_well(source,
                                    pickup_position.point.x,
                                    pickup_position.point.y,
                                    source.depth,
                                    speed_xy= speed_xy, 
                                    speed_z=sweep_speed)
            else:
                nav.move_inside_well(source,z=source.depth,speed_z=sweep_speed),
    
            nav.move_inside_well(well= source,
                                x = sweep_x, 
                                y = sweep_y,
                                speed_xy = sweep_speed)

            nav.move_to_well(well_dest,speed_xy,margin= 10)

            nav.move_inside_well(well= source,
                                x = sweep_x, 
                                y = sweep_y,
                                speed_xy = sweep_speed)        
            
        nav.move_to_safe_z()

