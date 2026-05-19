import random

import math
import random

from science_jubilee.labware.Labware import (Location,Point,Well)

from science_jubilee.navigation.deck_navigation import DeckNavigator
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

    Déplacer toute la logique géométrique dans Well ?
    Exemple:
    well.random_position()
    well.safe_sweep()

    Le Tool ne devrait pas connaître ne doit pas avoir accès a la géométrie
    mais Deck_navigation doit pouvoir utiliser les fonctions de well pour les données aux tools
    Utilité sur d'autres outils ?
    d'un point de vue pratique est ce vraiment problématique
    """

    @requires_active_tool
    def transfer(
        self,
        source: Well,
        destination: Well,
        *,
        speed: int = 2000,
        sweep_x: float = 5.0,
        sweep_y: float = 5.0,
        sweep_speed: float = 100.0,
        randomize_pickup: bool = False,
    ) -> None:
        """
        Transfer an object from source well to destination well.
        """
        pickup_x = source.x
        pickup_y = source.y
        pickup_z = source.depth

        rx = 0.0
        ry = 0.0

        if randomize_pickup:

            if source.diameter is None:
                raise ValueError(
                    "Randomized pickup requires a circular well "
                    "with a defined diameter."
                )

            r = (source.diameter / 2 ) * 0.7

            angle = random.uniform(0, 2 * math.pi)
            radius = random.uniform(0, r)

            rx = math.cos(angle) * radius
            ry = math.sin(angle) * radius

            pickup_x += rx
            pickup_y += ry

        pickup_position = Location(
            point=Point(
                pickup_x,
                pickup_y,
                pickup_z,
            ),
            resource=source,
        )

        navigation.move_to_target(source, z_from_top=0)
        navigation.move_to_target(pickup_position, speed_z=sweep_speed, travel_margin=0,safe_movement= False)

        sweep_target_x = pickup_x + sweep_x
        sweep_target_y = pickup_y + sweep_y

        if source.diameter is not None:

            max_r = (source.diameter / 2) * 0.85

            dx = sweep_target_x - source.x
            dy = sweep_target_y - source.y

            distance = math.sqrt(dx**2 + dy**2)

            if distance > max_r:

                scale = max_r/ distance

                dx *= scale
                dy *= scale

                sweep_target_x = source.x + dx
                sweep_target_y = source.y + dy

        sweep_position = Location(
            point=Point(
                sweep_target_x,
                sweep_target_y,
                pickup_z,
            ),
            resource=source,
        )

        navigation.move_to_target(sweep_position, speed_z=sweep_speed, travel_margin=0, safe_movement= False)
        navigation.move_to_target(source,z_from_top=0)

        destination_position = Location(
            point=Point(
                destination.x,
                destination.y,
                destination.depth,
            ),
            resource=destination,
        )

        navigation.move_to_target(destination_position,travel_margin= 0, safe_movement= True)

        destination_sweep = Location(
            point=Point(
                destination.x + sweep_x,
                destination.y + sweep_y,
                destination.depth,
            ),
            resource=destination,
        )

        navigation.move_to_target(destination_sweep,speed_z=sweep_speed,travel_margin=0, safe_movement= False)
        navigation.move_to_safe_z()


"""
    def transfert_to_all_well(source: str, destination: str)
    #prend des slots en paramètres pour remplir tous les puits automatiquement
    get labware in slot
    for wells in labware
        transfert(source, well)

"""    
