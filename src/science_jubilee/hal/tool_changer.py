from __future__ import annotations


class ToolChanger:
    """Tool actuation facade: lock/unlock, pickup, park, offsets."""

    def __init__(self, transport) -> None:
        self.transport = transport

    def tool_lock(self) -> None:
        self.transport.tool_lock()

    def tool_unlock(self) -> None:
        self.transport.tool_unlock()

    def pickup_tool(self, index: int) -> bool:
        return self.transport.select_tool(int(index))

    def park_tool(self) -> bool:
        return self.transport.park_tool()

    def get_active_tool_index(self) -> int:
        return self.transport.get_active_tool_index()

    def get_tools(self) -> dict:
        return self.transport.get_tools()

    def get_tool_offsets(self) -> dict:
        return self.transport.get_tool_offsets()

    def set_tool_offset(self, tool_idx: int, *, x: float | None = None, y: float | None = None, z: float | None = None) -> bool:
        return self.transport.set_tool_offset(tool_idx, x=x, y=y, z=z)
