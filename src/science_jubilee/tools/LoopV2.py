import random
import warnings
from typing import Tuple

import numpy as np

from science_jubilee.decks.Deck import Deck
from science_jubilee.navigation.deck_navigation import DeckNavigator
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.tools.Tool import Tool, requires_active_tool

deck: Deck
nav: DeckNavigator


class Inoculator(Tool):
    """A class representation of an inoculator.

    :param Tool: The base tool class
    :type Tool: :class:`Tool`
    """

    def __init__(self, index, name):
        """Constructor method"""
        super().__init__(index, name)


    
    
    @requires_active_tool
    def transfer(
        self,
        source:  str = None,
        destination: str = None,
        speed: int = 2000,
        sweep_x: float = 5,
        sweep_y: float = 5,
        sweep_z: float = 10,
        sweep_speed: float = 100,
        up_speed: float = 800,
        randomize_pickup: bool = False,
    ):
        #rédige l'entête de description de la fonction 

        if deck.slots[source].has_labware != True and deck.slots[destination].has_labware != True:
            pass

        if deck.slots[source].labware.wells != None and deck.slots[destination].labware.wells != None:
            pass

        #On récupère le puit source
        well_source =  deck.slots[source].labware.wells["A1"]

        #on traverse chacun des puits de wells: Dict[str, Well]
        for well_dest in deck.slots[str(source)].labware.wells:
            if (
                randomize_pickup
            ):  # to make sure we don't try to pickup from an empty region
                r = 20
                rx = random.randint(-r, r)
                ry = random.randint(-r, r)
                xs += rx
                ys += ry

            nav.move_to_well(well_source,z_from_bottom= 30)
            # slowly sweep in the reservoir to pick up duckweed
            # utilise location et donc move_to_well avec un écart random
            # utilisé driver pour move_to

            nav.move_to_well(well_dest,z_from_bottom=5)
            # utilisé Location pour ce déplacer dans le puits

    

    