from __future__ import annotations
from typing import Dict
from science_jubilee.tools.Tool import Tool


class ToolChanger:
    """Tool actuation facade: lock/unlock, load, pickup, park, offsets."""


    def __init__(self, transport) -> None:
        self.transport = transport
        tools: Dict[int, Tool]

    def load_tool(self,tool_idx: int,name: str, x: float = 0.0, y: float = 0.0, z: float = 0.0,) -> bool:
        self.transport.load_tool(tool_idx,name,x,y,z)
        

    def unload_tool(self, tool_idx: int) -> bool:
        self.transport.unload_tool(tool_idx)
        self.tools[tool_idx] = None

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

    #Ces getters récupère les données des tools
    #plutot que les objets tool
    #utilité potentiel: voir ce que la machine a enregistré
    def tools_state(self) -> dict:
        return self.transport.get_tools()
    
    #Il est préférable de retourner l'objet qui donnera de lui même l'accès aux données
    def get_tools(self) -> dict:
        return self.tools

    def state_tool_offsets(self) -> dict:
        return self.transport.get_tool_offsets()

    #l'offset est définit lors de load_tool, pas besoin de l'avoir ici ?
    def set_tool_offset(self, tool_idx: int, *, x: float | None = None, y: float | None = None, z: float | None = None) -> bool:
        return self.transport.set_tool_offset(tool_idx, x=x, y=y, z=z)

