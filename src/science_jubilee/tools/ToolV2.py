from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Dict, Iterator

from science_jubilee.hal.tool_changer import ToolChanger


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


@dataclass(slots=True, repr=False)
class Tool:
    """
    Base runtime representation of a machine tool.
    """

    index: int
    name: str

    is_active_tool: bool = False
    offset: tuple[float, float, float] | None = None
    
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
        Can be very useful when you use a tool which required another system to be launched
        """

        pass


    # ------------------------------------------------------------------
    # Tool offset
    # ------------------------------------------------------------------

    def set_offset(self,x: float,y: float,z: float) -> None:
        """
        Set the tool offset values.

        This only updates the runtime state.
        Hardware synchronization must be handled
        by ToolChanger or the HAL layer.
        """
        self.offset = (x, y, z)
    
    def get_offset(self) -> tuple:
        return self.offset


    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def activate(self) -> None:
        self.is_active_tool = True

    def deactivate(self) -> None:
        self.is_active_tool = False


# ======================================================================
# ToolSlot
# ======================================================================


@dataclass(slots=True, repr=False)
class ToolSlot:
    """
    Represent a physical slot in the tool park.
    """

    slot_index: str

    offset: tuple[float, ...] = ()

    tool: Tool | None = None

    @property
    def is_empty(self) -> bool:
        return self.tool is None

    def load_tool(self, tool: Tool) -> None:
        self.tool = tool

    def unload_tool(self) -> None:
        self.tool = None

    def get_tool(self) -> Tool:
        if self.tool is None:
            raise ValueError(
                f"No tool loaded in slot "
                f"{self.slot_index}"
            )
        return self.tool

    def __repr__(self):
        if self.tool is None:
            return (
                f"ToolSlot("
                f"{self.slot_index}, "
                f"empty"
                f")"
            )

        return (
            f"ToolSlot("
            f"{self.slot_index}, "
            f"tool={self.tool.name}"
            f")"
        )


# ======================================================================
# ToolSlotSet
# ======================================================================


@dataclass(slots=True, repr=False)
class ToolSlotSet:
    """
    Domain-oriented collection of tool slots.
    """

    slots: Dict[str, ToolSlot] = field(
        default_factory=dict
    )

    def __iter__(self) -> Iterator[ToolSlot]:
        return iter(self.slots.values())

    def __len__(self) -> int:
        return len(self.slots)

    def __contains__(self, slot_id: str) -> bool:
        return slot_id in self.slots

    def __getitem__(self, identifier):
        if isinstance(identifier, str):
            return self.get_slot(identifier)
        if isinstance(identifier, int):
            return list(self.slots.values())[identifier]

        raise TypeError(
            f"Unsupported identifier type: "
            f"{type(identifier)}"
        )

    def __repr__(self):
        return (
            f"ToolSlotSet("
            f"slots={list(self.slots.keys())}"
            f")"
        )

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def get_slot(self, slot_id: str) -> ToolSlot:
        return self.slots[slot_id]

    def get_slots(self) -> list[ToolSlot]:
        return list(self.slots.values())

    # ------------------------------------------------------------------
    # Tools
    # ------------------------------------------------------------------

    def get_tool(self, slot_id: str) -> Tool:
        return self.get_slot(slot_id).get_tool()

    def has_tool(self, slot_id: str) -> bool:
        return not self.get_slot(slot_id).is_empty


# ======================================================================
# ToolPark
# ======================================================================


@dataclass(slots=True, repr=False)
class ToolPark(ToolSlotSet):
    """
    Runtime representation of the tool park.
    """

    tool_changer: ToolChanger | None = None
    active_tool: Tool | None = None

    def load_tool(self,tool: Tool,slot_id: str) -> None:
        slot = self.get_slot(str(slot_id))
        slot.load_tool(tool)
        self.tool_changer.load_tool(tool.index, tool.name, tool.offset[0],tool.offset[1],tool.offset[2])

    def unload_tool(self, slot_id: str) -> None:
        slot = self.get_slot(str(slot_id))
        slot.unload_tool()
        self.tool_changer.unload_tool(slot_id)

    # ------------------------------------------------------------------
    # Active tool management
    # ------------------------------------------------------------------

    def set_active_tool(self, slot_id: str) -> Tool:
        tool = self.get_tool(slot_id)

        if self.active_tool is not None:
            self.active_tool.deactivate()

        tool.activate()
        self.active_tool = tool

        return tool

    def clear_active_tool(self) -> None:
        if self.active_tool is not None:
            self.active_tool.deactivate()

        self.active_tool = None

    # ------------------------------------------------------------------
    # Tool changer
    # ------------------------------------------------------------------

    def pickup_tool(self, slot_id: str) -> Tool:
        tool = self.set_active_tool(slot_id)

        if self.tool_changer is not None:
            self.tool_changer.pickup_tool(tool)

        return tool

    def park_tool(self) -> None:
        if self.active_tool is None:
            raise ToolStateError(
                "No active tool to park."
            )

        if self.tool_changer is not None:
            self.tool_changer.park_tool(
                self.active_tool
            )

        self.active_tool.deactivate()
        self.active_tool = None
