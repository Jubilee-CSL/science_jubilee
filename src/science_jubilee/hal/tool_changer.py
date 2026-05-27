from __future__ import annotations
from typing import Dict
from science_jubilee.tools.Tool import Tool


class ToolChanger:
    """Tool actuation facade: lock/unlock, load, pickup, park, offsets."""
    tools: Dict[int, Tool] = { 0 : None, 1 : None, 2 : None, 3 : None}


    def __init__(self, transport) -> None:
        self.transport = transport

    def load_tool(self,tool: Tool) -> bool:
        if tool.index not in self.tools:
            raise ValueError(f"Invalid tool slot {tool.index}")

        if self.tools[tool.index] != None:
            raise ValueError(f"Tool slot {tool.index} already occupied")
            
        self.tools[tool.index] = tool
        self.transport.load_tool(tool.index,tool.name,tool.x,tool.y,tool.z)

    def unload_tool(self, tool_idx: int) -> bool:
        if tool_idx not in self.tools:
            raise ValueError(f"Invalid tool slot {tool_idx}")

        if self.tools[tool_idx] == None:
            raise ValueError(f"There is no tool at this slot")
        
        if self.get_active_tool_index == tool_idx:
            self.park_tool()

        self.transport.unload_tool(tool_idx)
        self.tools[tool_idx] = None

    def tool_lock(self) -> None:
        self.transport.tool_lock()

    def tool_unlock(self) -> None:
        self.transport.tool_unlock()

    def pickup_tool(self, tool_idx: int) -> bool:
        if self.get_active_tool_index == tool_idx:
            raise ValueError(f"Tool is already pick up")
        
        if tool_idx not in self.tools:
            raise ValueError(f"Invalid tool slot {tool_idx}")
        
        if self.tools[tool_idx] == None:
            raise ValueError(f"There is no tool at this slot")
        
        self.tools[tool_idx].is_active_tool = True   
        return self.transport.select_tool(int(tool_idx))

    def park_tool(self) -> bool:
        tool_idx = self.get_active_tool_index()
        self.tools[tool_idx].is_active_tool = False
        return self.transport.park_tool()

    def get_active_tool_index(self) -> int:
        return self.transport.get_active_tool_index()

    def state_tools(self) -> dict:
        return self.transport.state_tools()
    
    def state_tool_offsets(self) -> dict:
        return self.transport.state_tool_offsets()

    def get_tools(self) -> dict:
        return self.tools

    #Should only be used by load_tool
    #User shouldnt have access to it
    #Modifying a tool_offset, would mean to create a new tool
    #Discuss about this function
    def set_tool_offset(self, tool_idx: int, *, x: float | None = None, y: float | None = None, z: float | None = None) -> bool:
        return self.transport.set_tool_offset(tool_idx, x=x, y=y, z=z)

    """
    Il pourrait être intéressant d'avoir une fonction qui check 
    la synchronisation des 2 dictionnaires
    def sync(self):
        active_tool_index = self.get_active_tool_index
        if self.tools[active_tool_index].is_active_tool == False
            raise ValueError(f"inter dictionnary is not in sync with codespace")
        etc
    """