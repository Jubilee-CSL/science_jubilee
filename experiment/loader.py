"""
Il pourra évoluer plus tard pour :

charger MongoDB ;
charger Altar ;
charger une interface graphique.

"""



from __future__ import annotations

import json
from pathlib import Path

from experiment.experience import Experience
from experiment.registry import Registry
from science_jubilee.decks import Deck

class ExperimentLoader:
    """
    Charge une expérience depuis un fichier JSON.

    Responsabilités
    ----------------
    - Lecture du fichier JSON
    - Construction de l'Experiment
    - Construction des Task et Action
    - Chargement des paramètres
    """

    # ---------------------------------------------------------

    @classmethod
    def load(cls,experience_file: str | Path,deck_file: str | Path | None = None) -> Experience:

        experience_file = Path(experience_file)

        with experience_file.open("r",encoding="utf-8") as file:
            config = json.load(file)

        experience = Experience(
            name=config["name"],
            description=config.get("description", ""),
            author=config.get("author", ""),
            version=config.get("version", "1.0"),
            parameters=config.get("parameters", {}),
        )

        for node in config.get("sequence", []):
            cls._add_node(
                experience,
                node,
            )

        deck = Deck(deck_file)

        return experience, deck

    # ---------------------------------------------------------

    @classmethod
    def _add_node(
        cls,
        experience: Experience,
        node: dict,
    ):

        identifier = node["id"]

        parameters = node.get(
            "parameters",
            {},
        )

        if not Registry.exists(identifier):

            raise ValueError(

                f"Unknown node '{identifier}'."

            )

        experience.add(

            Registry.create(

                identifier,

                **parameters,

            )

        )

#Exemple de Json associé 
"""
{
    "name": "Transfer lens",

    "description": "Simple demonstration",

    "author": "Pierre",

    "version": "1.0",

    "sequence": [

        {

            "id": "home"

        },

        {

            "id": "transfer_lens",

            "parameters": {

                "source": "Plate1:A1",

                "destination": "Plate2"

            }

        },

        {

            "id": "wait",

            "parameters": {

                "duration": 2

            }

        },

        {

            "id": "capture_image",

            "parameters": {

                "camera": "Top"

            }

        }

    ]
}
"""