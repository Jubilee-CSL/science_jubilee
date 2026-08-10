from __future__ import annotations

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

    # ------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------

    def __init__(self, transport) -> None:

        self.transport = transport
        # Instance runtime state
        self.tools: Dict[int, Optional[Tool]] = {
            0: None,
            1: None,
            2: None,
            3: None,
        }
        duet_tools = transport.get_tools()
        for i in range(4):
            tool_name = duet_tools[i]["name"]
            """
            if tool_name == "Inoculator":
                self.tools[i] = Inoculator(i,tool_name)
            """
            if tool_name != "None":
                self.tools[i] = Tool(i, tool_name)

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

    def pickup_tool(self, tool_idx: int) -> bool:
        if tool_idx not in self.tools:
            raise ToolSlotError(f"Invalid tool slot {tool_idx}")

        tool = self.tools[tool_idx]

        if tool is None:
            raise ToolSlotError(f"No tool loaded in slot {tool_idx}")

        if self.get_active_tool_index() == tool_idx:
            return True

        if list(self.get_tool_offset(tool_idx)) == [0.0, 0.0, -400.0]:
            raise ToolStateError("Tool offset must be configured")

        self.park_tool()

        success = self.transport.select_tool(tool_idx)

        if success:
            self.tools[tool_idx].activate()
        return success

    def park_tool(self) -> bool:
        tool_idx = self.get_active_tool_index()

        if tool_idx < 0:
            return True

        tool = self.tools.get(tool_idx)
        if tool is None:
            return True

        success = self.transport.park_tool()

        if success:
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
    def get_tool(self, tool_idx) -> Tool:
        if tool_idx not in self.tools:
            raise ToolSlotError(f"Invalid tool slot {tool_idx}")

        tool = self.tools[tool_idx]

        if tool is None:
            raise ToolSlotError(f"No tool loaded in slot {tool_idx}")

        return tool

    def get_tools(self) -> dict:
        """
        Query transport tool state.
        """
        return self.transport.get_tools()

    def get_tool_offsets(self) -> dict:
        """
        Query transport tool offsets.
        """
        return self.transport.get_tool_offsets()

    def get_tool_offset(self, tool_idx):
        offsets = self.transport.get_tool_offsets()
        return offsets[tool_idx]
