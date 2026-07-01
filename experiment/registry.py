from __future__ import annotations

from typing import Type

from experiment.task import Task
from experiment.action import Action, ExperimentNode


"""
Registry.register_tool(...)
Registry.register_observer(...)
Registry.register_validator(...)
Registry.register_executor(...)
"""

class Registry:
    """
    Registre central du framework.

    Toutes les Task et Action sont enregistrées grâce au
    décorateur @Registry.register("identifier").
    """

    _nodes: dict[str, Type[ExperimentNode]] = {}
    _tasks: dict[str, Type[Task]] = {}
    _actions: dict[str, Type[Action]] = {}

    # ---------------------------------------------------------

    @classmethod
    def register(cls, identifier: str):
        """
        Décorateur d'enregistrement.

        Exemple
        -------
        @Registry.register("transfer_lens")
        class TransferLens(Task):
            ...
        """

        def decorator(obj):

            if identifier in cls._nodes:
                raise ValueError(
                    f"Identifier '{identifier}' already registered."
                )

            cls._nodes[identifier] = obj

            if issubclass(obj, Task):
                cls._tasks[identifier] = obj

            elif issubclass(obj, Action):
                cls._actions[identifier] = obj

            else:
                raise TypeError(
                    f"{obj.__name__} must inherit Task or Action."
                )

            obj.identifier = identifier

            return obj

        return decorator

    # ---------------------------------------------------------

    @classmethod
    def create(cls, identifier: str, **kwargs):

        if identifier not in cls._nodes:
            raise ValueError(
                f"Unknown identifier '{identifier}'."
            )

        return cls._nodes[identifier](**kwargs)

    # ---------------------------------------------------------

    @classmethod
    def exists(cls, identifier: str):

        return identifier in cls._nodes

    # ---------------------------------------------------------

    @classmethod
    def task(cls, identifier: str):

        return cls._tasks[identifier]

    # ---------------------------------------------------------

    @classmethod
    def action(cls, identifier: str):

        return cls._actions[identifier]

    # ---------------------------------------------------------

    @classmethod
    def nodes(cls):

        return cls._nodes.copy()

    # ---------------------------------------------------------

    @classmethod
    def tasks(cls):

        return cls._tasks.copy()

    # ---------------------------------------------------------

    @classmethod
    def actions(cls):

        return cls._actions.copy()