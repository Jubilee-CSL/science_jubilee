import random
import warnings
from typing import Tuple

import numpy as np

from science_jubilee.navigation.deck_navigation import DeckNavigator
from science_jubilee.labware.Labware import Well, Location
from science_jubilee.tools.Tool import Tool, requires_active_tool


navigation: DeckNavigator


class Inoculator(Tool):
    """A class representation of an inoculator.

    :param Tool: The base tool class
    :type Tool: :class:`Tool`
    """

    def __init__(self, index, name):
        """Constructor method"""
        super().__init__(index, name)

    """
    transfert doit accepter en paramètres des puits ou des slots/labware ?
    Exemple de fonction déveleopper ici: transfert d'un puit a un autre
    la position des puits a supposé comme le centre du puits
    """

    @requires_active_tool
    def transfer(
        self,
        source:  Well = None,
        destination: Well = None,
        speed: int = 2000,
        sweep_x: float = 5,
        sweep_y: float = 5,
        sweep_speed: float = 100,
        randomize_pickup: bool = False,
    ):
        #On créé une Location, pour que la machine se déplace a la surface de l'eau
        position: Location
        position.x = source.x
        position.y = source.y
        position.z = source.depth
        #si le randomize_pickup est actif
        #On créé une Location qui sera une position aléatoire dans le puit
        if (
                randomize_pickup
            ):  # to make sure we don't try to pickup from an empty region
                r = source.diameter / 3 # par sécurité, on réduit le rayon d'action possible 
                rx = random.randint(-r, r)
                ry = random.randint(-r, r)

                position.x = source.x + rx
                position.y = source.y + ry

        #se déplace vers la source, 
        #QUESTION z_from top le haut de la Labware ou la surface du liquide
        navigation.move_to_well(source, z_from_top=0)

        #Tester la vitesse optimale pour limiter l'éparpillement des lentilles
        navigation.move_to_well(position, speed = sweep_speed)
        #move to well a une sécurité move to safe Z, qui la rend inutilisable
        #necessité d'avoir une fonction du style move to location sans safe z

        #effectue le balayage
        #créé une position pour chaque mouvement de balayage
        #TODO ajouter une sécurité pour que  sweep ne nous emmene pas en dehors du puit
        #sweep pourrait etre un valeur borné 
        #exemple if well.diameter / 2 - rx - 5  < sweep => sweep = 2
        position.x += sweep_x
        position.y += sweep_y
        navigation.move_to_well(position, speed = sweep_speed)

        #vitesse optimale a tester
        #remonte brusquement pour conserver la lentille dans la boucle
        navigation.move_to_well(source, z_from_top=0)
        
        #doit se déplacer a la surface
        position.x = destination.x
        position.y = destination.y
        position.z = destination.depth
        navigation.move_to_well(position)

        #effectue le balayage
        #créé une position pour chaque mouvement de balayage
        position.x += sweep_x
        position.y += sweep_y
        navigation.move_to_well(position, speed = sweep_speed)

"""
    def transfert_to_all_well(source: str, destination: str)
    #prend des slots en paramètres pour remplir tous les puits automatiquement
    get labware in slot
    for wells in labware
        transfert(source, well)

"""    