from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field

from experiment.plan import ExecutionPlan
from experiment.runner import ExperimentCompiler
from experiment.action import ExperimentNode



# ======================================================
# Experiment
# ======================================================
@dataclass
class Experiment:
    """
    Décrit une expérience.

    Une expérience est simplement une séquence ordonnée
    de Task et/ou d'Action.

    Elle ne réalise aucune exécution.
    """

    name: str

    description: str = ""

    author: str = ""

    version: str = "1.0"

    parameters: dict = field(default_factory=dict)

    metadata: dict = field(default_factory=dict)

    sequence: list[ExperimentNode] = field(default_factory=list)

    # ------------------------------------------------------------------

    def add(self, node: ExperimentNode):

        self.sequence.append(node)

    # ------------------------------------------------------------------

    def insert(self, index: int, node: ExperimentNode):

        self.sequence.insert(index, node)

    # ------------------------------------------------------------------

    def remove(self, node: ExperimentNode):

        self.sequence.remove(node)

    # ------------------------------------------------------------------

    def clear(self):

        self.sequence.clear()

    # ------------------------------------------------------------------

    def compile(self) -> tuple[ExecutionPlan, ExecutionPlan]:
        """
        Retourne :

            plan_complete
            plan_mock
        """

        compiler = ExperimentCompiler()

        return compiler.compile(self)
        