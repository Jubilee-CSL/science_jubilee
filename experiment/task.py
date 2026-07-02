# execution/task.py

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field

from .action import Action, ExperimentNode
from experiment.task import Task
from experiment.plan import ExecutionPlan

from science_jubilee.navigation.deck_navigation import DeckNavigator

from experiment.registry import Registry
from experiment.action import *

@dataclass
class Task(ExperimentNode):
    """
    Une Task représente une opération scientifique.

    Elle ne pilote jamais directement la machine.
    Son rôle est de construire une partie de l'ExecutionPlan.
    """

    name: str

    description: str = ""

    enabled: bool = True

    parameters: dict = field(default_factory=dict)

    metadata: dict = field(default_factory=dict)

    #Les requirements seront utilisé pour vérifier la présence des ressources indispensables
    #Outil de communication pour le développeur

    required_tools: list[str] = field(default_factory=list)

    required_observers: list[str] = field(default_factory=list)

    required_modules: list[str] = field(default_factory=list)

    @abstractmethod
    def compile(self) -> list[Action]:
        """
        Construit les Actions nécessaires à cette tâche.

        La Task ajoute simplement des Actions dans le plan.

        Aucune commande n'est exécutée ici.

        Créé sa tache pour y ajouter des actions
        Les taches ne doivent pas devenir trop complexe
        
        """
        ...


#Exemple de contruction de tache
#Dans un cas réel les coordonnées seront obtenue a partir de DeckNavigation
#les coordonnées étant des paramètres on peux y placé n'importe quoi

@dataclass
@Registry.register("transfer_lens")
class TransferLens(Task):

    parameters = {
        "well_source": str,
        "slot_source": str ,
        "well_destination": str,
        "slot_destination": str,
        "speed_xy": float,
        "speed_z": float,
        "margin": float,
        "random": bool,
        "sweep_x": float,
        "sweep_y":float,
        "sweep_speed":float,
        }
    
    required_tools=["Inoculator"]
    required_modules=["DeckNavigator"]


    def compile(self, plan: ExecutionPlan):
        
        plan.add(
            PickupTool(name="Pickup Inoculator",tool_name="Inoculator")
        )
        plan.add(
            MoveToWell(name="Got to source",
                       well_name = self.parameters["well_source"],
                       slot_id = self.parameters["slot_source"],
                       speed_xy = self.parameters["speed_xy"],
                       speed_z= self.parameters["speed_z"],
                       margin= self.parameters["margin"],
                       random= self.parameters["random"]))


        plan.add(
            MoveToWaterLevel(
                well_name=self.parameters["source_well"],
                slot_id = self.parameters["slot_source"],
                surface=True,
                speed_z=self.parameters["speed_z"],
            )
        )

        plan.add(
            MoveInsideWell(
                well_name=self.parameters["source_well"],
                slot_id = self.parameters["slot_source"],
                x=self.parameters["sweep_x"],
                y=self.parameters["sweep_y"],
                speed_xy=self.parameters["sweep_speed"],
            )
        )

        plan.add(
            MoveToSafeZ(
                margin=self.parameters["margin"],
                speed=self.parameters["speed_z"],
            )
        )

        # Destination
        plan.add(
            MoveToWell(name="Got to source",
                       well_name = self.parameters["well_destination"],
                       slot_id = self.parameters["slot_destination"],
                       speed_xy = self.parameters["speed_xy"],
                       speed_z= self.parameters["speed_z"],
                       margin= self.parameters["margin"],
                       random= self.parameters["random"])
                       )
        

        plan.add(
            MoveToWaterLevel(
                well_name=self.parameters["well_destination"],
                slot_id = self.parameters["slot_source"],
                speed_z=self.parameters["speed_z"],
            )
        )

        plan.add(
            MoveInsideWell(
                well_name=self.parameters["well_destination"],
                slot_id = self.parameters["slot_source"],
                x=self.parameters["sweep_x"],
                y=self.parameters["sweep_y"],
                speed_xy=self.parameters["sweep_speed"],
            )
        )

        plan.add(
            MoveToSafeZ(
                margin=self.parameters["margin"],
                speed=self.parameters["speed_z"],
            )
        )