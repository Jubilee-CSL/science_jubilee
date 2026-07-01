# execution/task.py

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .action import Action, ExperimentNode

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