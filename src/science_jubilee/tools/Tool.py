from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any


# ======================================================================
# Exceptions
# ======================================================================


class ToolStateError(Exception):
    """
    Raised when a tool is in an invalid runtime state.
    """

    pass


class ToolConfigurationError(Exception):
    """
    Raised when a tool configuration is invalid.
    """

    pass


# ======================================================================
# Decorators
# ======================================================================


def requires_active_tool(func):
    """
    Ensure the tool is currently active.
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):

        if not self.is_active_tool:

            raise ToolStateError(
                f"Tool {self.name} is not the active tool."
            )

        return func(self, *args, **kwargs)

    return wrapper


# ======================================================================
# Tool
# ======================================================================

"""
Architecture
ToolPark
 └── ToolSlot
      └── Tool
risque de conflit avec les macros, a étudier 


    class ToolStatus(Enum):
    PARKED
    LOADED
    ACTIVE
    ERROR
    CALIBRATING

    capabilities: set[ToolCapability]

    tool.validate_before_motion()
    # TODO:
    # add a park tool method that every tool config can define to do things that need to be done pre or post parking
    # ex: make sure pipette has dropped tips before parking

    #si un outil utilise des modules externes s'assurer que l'utilisateur en est connaisance
    def show_requierement(self):
        # a débattre de l'utilité de cette fonction
        pass

"""

@dataclass(slots=True, repr=False)
class Tool:
    """
    Base runtime representation of a machine tool.
    """

    index: int
    name: str

    is_active_tool: bool = False
    
    tool_offset_is_set: bool = False

    configuration: dict[str, Any] = field(
        default_factory=dict,
    )

    def __post_init__(self):
        if not isinstance(self.index, int):

            raise ToolConfigurationError(
                "Tool index must be an integer."
            )

        if not isinstance(self.name, str):

            raise ToolConfigurationError(
                "Tool name must be a string."
            )

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"index={self.index}, "
            f"name={self.name}"
            f")"
        )

    # ------------------------------------------------------------------
    # Runtime lifecycle
    # ------------------------------------------------------------------

    def post_load(self) -> None:
        """
        Called after the tool is associated with the machine.
        """

        pass
 
    
