from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from science_jubilee.tools.Tool import Tool

# ------------------------------------------------------------------
# Exceptions
# ------------------------------------------------------------------

class ToolError(Exception):
    """Base tool exception."""

class ToolSlotError(ToolError):
    """Invalid or unavailable tool slot."""

class ToolStateError(ToolError):
    """Invalid tool state transition."""

class ToolSyncError(ToolError):
    """Transport and local cache are out of sync."""

# ------------------------------------------------------------------
# Tool changer
# ------------------------------------------------------------------


class ToolChanger:
    """
    High-level tool orchestration facade.

    Responsibilities
    ----------------
    - Tool lifecycle management
    - Tool selection / parking
    - Tool lock actuation
    - Synchronization with transport layer
    - Runtime validation

    Notes
    -----
    ToolChanger handles:
    - state consistency
    - validation
    - orchestration
    """

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(self,transport,slots: int = 4,) -> None:

        self.transport = transport
        # Instance runtime state
        self.tools: Dict[int, Optional[Tool]] = {
            idx: None
            for idx in range(slots)
        }

    # ------------------------------------------------------------------
    # Tool lifecycle management
    # ------------------------------------------------------------------

    #A terme il pourrait y avoir une fonction create_tool_from_config
    #qui utilserai load_tool pour automatisé le processus
    def load_tool(self,tool: Tool,) -> None:
        """
        Register and configure a tool.

        Notes
        -----
        This operation:
        - validates slot availability
        - registers tool locally
        - configures transport firmware
        """

        if tool.index not in self.tools:
            raise ToolSlotError(f"Invalid tool slot {tool.index}")

        if self.tools[tool.index] is not None:
            raise ToolSlotError(f"Tool slot {tool.index} already occupied")

        self.transport.load_tool(tool.index,tool.name,
                                 tool.offset.x,tool.offset.y,tool.offset.z,)

        self.tools[tool.index] = tool

    def unload_tool(self,tool_idx: int,) -> None:
        """
        Remove a tool from a slot.
        """

        if tool_idx not in self.tools:
            raise ToolSlotError(f"Invalid tool slot {tool_idx}")

        tool = self.tools[tool_idx]

        if tool is None:
            raise ToolSlotError(
                f"No tool loaded in slot {tool_idx}"
            )

        if self.get_active_tool_index() == tool_idx:
            self.park_tool()

        self.transport.unload_tool(
            tool_idx
        )

        self.tools[tool_idx] = None

    # ------------------------------------------------------------------
    # Tool actuation
    # ------------------------------------------------------------------

    def tool_lock(self) -> None:
        self.transport.tool_lock()

    def tool_unlock(self) -> None:
        self.transport.tool_unlock()

    # ------------------------------------------------------------------
    # Tool selection
    # ------------------------------------------------------------------

    def pickup_tool(self,tool_idx: int,) -> bool:
        if tool_idx not in self.tools:
            raise ToolSlotError(f"Invalid tool slot {tool_idx}")

        tool = self.tools[tool_idx]

        if tool is None:
            raise ToolSlotError(f"No tool loaded in slot {tool_idx}")

        if self.get_active_tool_index() == tool_idx:
            raise ToolStateError(f"Tool {tool_idx} already active")

        if not tool.tool_offset_is_set:
            raise ToolStateError("Tool offset must be configured")

        success = self.transport.select_tool(tool_idx)

        if success:
            tool.activate()
        return success

    def park_tool(self) -> bool:
        tool_idx = self.get_active_tool_index()

        if tool_idx < 0:
            return True

        tool = self.tools.get(tool_idx)
        success = self.transport.park_tool()

        if success and tool is not None:
            tool.deactivate()
        return success

    def get_active_tool_index(self) -> int:
        return int(self.transport.get_active_tool_index())

    def get_active_tool(self) -> Optional[Tool]:
        tool_idx = self.get_active_tool_index()

        if tool_idx < 0:
            return None
        return self.tools.get(tool_idx)

    # ------------------------------------------------------------------
    # Tool state inspection
    # ------------------------------------------------------------------

    def get_tools(self) -> Dict[int, Optional[Tool]]:
        """
        Return local runtime tool registry.
        """
        return self.tools

    def state_tools(self) -> dict:
        """
        Query transport tool state.
        """
        return self.transport.state_tools()

    def state_tool_offsets(self) -> dict:
        """
        Query transport tool offsets.
        """
        return self.transport.state_tool_offsets()

    # ------------------------------------------------------------------
    # Tool calibration
    # ------------------------------------------------------------------

    def set_tool_offset(self,tool_idx: int,*,
        x: float | None = None,
        y: float | None = None,
        z: float | None = None,
    ) -> bool:
        """
        Update firmware tool offsets.

        Notes
        -----
        Should generally only be called
        during tool calibration/setup.
        """

        tool = self.tools.get(tool_idx)

        if tool is None:
            raise ToolSlotError(f"No tool in slot {tool_idx}")

        success = self.transport.set_tool_offset(tool_idx,x=x,y=y,z=z,)

        if success:
            if x is not None:
                tool.offset.x = x

            if y is not None:
                tool.offset.y = y

            if z is not None:
                tool.offset.z = z
        return success

    # ------------------------------------------------------------------
    # Synchronization / validation
    # ------------------------------------------------------------------

    def sync(self) -> None:
        """
        Validate synchronization between
        local runtime cache and transport state.
        """

        active_tool_idx = (self.get_active_tool_index())

        for idx, tool in self.tools.items():
            if tool is None:
                continue

            expected_active = (idx == active_tool_idx)

            if tool.is_active_tool != expected_active:
                raise ToolSyncError(
                    f"Tool {idx} desynchronized "
                    f"with transport state"
                )

"""
Peuvent devenir utile mais merite réflexion
    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def has_tool(self,tool_idx: int,) -> bool:

        return (tool_idx in self.tools and self.tools[tool_idx] is not None)

    def is_tool_active(self,tool_idx: int,) -> bool:

        return (self.get_active_tool_index()== tool_idx)
"""