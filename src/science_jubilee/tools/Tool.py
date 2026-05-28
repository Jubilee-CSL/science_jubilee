from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps

from science_jubilee.navigation.deck_navigation import DeckNavigator


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
# ToolOffset
# ======================================================================


@dataclass(slots=True)
class ToolOffset:
    """
    Tool offset in machine coordinates.
    """

    x: float = None
    y: float = None
    z: float = None

    def as_tuple(self) -> tuple[float, float, float]:

        return (self.x,self.y,self.z,)

# ======================================================================
# Tool
# ======================================================================

"""
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

    This class is intended to be inherited by all
    runtime tools.
    """
    nav: DeckNavigator
    index: int
    name: str

    offset: ToolOffset = field(
        default_factory=ToolOffset
    )

    is_active_tool: bool = False

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

    @property
    def tool_offset_is_set(self) -> bool:
        return self.offset != ToolOffset()
    # ------------------------------------------------------------------
    # Runtime lifecycle
    # ------------------------------------------------------------------

    def post_load(self) -> None:
        """
        Called after the tool is associated
        with the machine.
        """

        pass

        # ------------------------------------------------------------------
    # Runtime state
    # ------------------------------------------------------------------

    def activate(self) -> None:
        self.is_active_tool = True

    def deactivate(self) -> None:
        self.is_active_tool = False

    # ------------------------------------------------------------------
    # Tool offset
    # ------------------------------------------------------------------

    def set_offset(
        self,
        x: float,
        y: float,
        z: float,
    ) -> None:
        """
        Set tool offset values.

        This only modifies runtime state.
        Hardware synchronization must be
        handled by ToolChanger or HAL.
        """

        self.offset.x = float(x)
        self.offset.y = float(y)
        self.offset.z = float(z)

    def get_offset(self) -> ToolOffset:
        return self.offset

    def get_offset_tuple(
        self,
    ) -> tuple[float, float, float]:
        return self.offset.as_tuple()

    def reset_offset(self) -> None:
        self.offset = ToolOffset()

"""
    # ------------------------------------------------------------------
    # Axis shortcuts
    # ------------------------------------------------------------------

    @property
    def x(self) -> float:
        return self.offset.x

    @property
    def y(self) -> float:
        return self.offset.y

    @property
    def z(self) -> float:
        return self.offset.z
"""