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

    @requires_active_tool
    def transfer(self, source: Well, destination: Well,
        *,
        speed: int = 2000,
        sweep_x: float = 5.0, sweep_y: float = 5.0, sweep_speed: float = 100.0,
        randomize_pickup: bool = False,
    ) -> None:
        """
        Transfer an object from source well to destination well.
        """

        #Définition de la position de départ, 
        #on cherche a atteindre la surface de l'eau dans le puit
        #possiblement ajouter un attribut surface au puits ou
        #définir une quantité d'eau que l'utilisateur doit respecter ???
        pickup_position = Location(
            point=Point(
                source.x,
                source.y,
                source.depth,
            ),
            resource=source,
        )

        if randomize_pickup:
            pickup_position = source.random_point(source.depth, safety_margin= 0.8)

        #Déplacement vers la position définit comme position de départ
        #tester la vitesse de optimal pour ne pas pousser les lentilles
        navigation.move_to_target(pickup_position, 
                                  speed_z=sweep_speed, 
                                  travel_margin=4,safe_movement= True)

        #Test de validité du mouvement et 
        #Retour de la position finale du balayage
        #possibilité d'améliorer la fonction pour obtenir une correction automatique
        sweep_position = source.safe_sweep(start_point= pickup_position, 
                sweep_x=sweep_x, sweep_y=sweep_y)

        #Mouvement de balayge
        #tester la vitesse de optimal pour attraper la lentille
        navigation.move_to_target(sweep_position,
            speed_z=sweep_speed, 
            travel_margin=0, safe_movement= False)

        #Définition de la position de départ, 
        #on cherche a atteindre la surface de l'eau dans le puit
        destination_position = Location(
            point=Point(
                destination.x,
                destination.y,
                destination.depth,
            ),
            resource=destination,
        )

        #Déplacement vers la source
        navigation.move_to_target(destination_position,
            travel_margin= 0, safe_movement= True)

        sweep_position = destination.safe_sweep(
            start_point= destination_position, 
            sweep_x=sweep_x, sweep_y=sweep_y)

        #tester la vitesse de optimal pour retirer la lentille
        navigation.move_to_target(sweep_position,speed_z=sweep_speed,travel_margin=0, safe_movement= False)
        navigation.move_to_safe_z()



    def transfert_to_all_well(self, source: str, destination: str) -> None:
    #prend des slots en paramètres pour remplir tous les puits automatiquement
        well_source = navigation.get_well(source,"A1")
        labware_destination = navigation.get_labware_in_slot(destination)
        for well in labware_destination:
            self.transfer(well_source, well)

