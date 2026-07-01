from __future__ import annotations

from dataclasses import dataclass, field

from experiment.action import Action

@dataclass
class ExecutionBundle:
    """
    Ensemble des plans produits par la compilation.
    """
    complete: ExecutionPlan

    mock: ExecutionPlan


@dataclass
class ExecutionPlan:

    name: str

    parameters: dict = field(default_factory=dict)

    actions: list[Action] = field(default_factory=list)
     

    # -------------------------------------------------------

    def add(self, action: Action):

        self.actions.append(action)

    # -------------------------------------------------------

    def extend(self, actions: list[Action]):

        self.actions.extend(actions)

    # -------------------------------------------------------

    def __iter__(self):

        return iter(self.actions)

    # -------------------------------------------------------

    def __len__(self):

        return len(self.actions)

    # -------------------------------------------------------

    def copy(self):

        return ExecutionPlan(
            name=self.name,
            parameters=self.parameters.copy(),
            actions=self.actions.copy(),
        )