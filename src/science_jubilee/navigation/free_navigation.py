from __future__ import annotations

from typing import Optional, Union
from enum import Enum

from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.hal.tool_changer import ToolChanger
from science_jubilee.tools.Tool import Tool


class FreeNavigator:
    """Free-form motion: jog, home, tool operations. No deck geometry.

    Example::

        transport = HTTPTransport(address="10.0.3.48")
        driver = MotionDriver(transport)
        tc = ToolChanger(transport)
        nav = FreeNavigator(driver, tc)
        nav.move_to(x=150, y=150)
        nav.pickup_tool(0)
    """

    def __init__(self, driver: MotionDriver, tool_changer: ToolChanger) -> None:
        self.driver = driver
        self.tool_changer = tool_changer

    # ------------------------------------------------------------------
    # Absolute motion
    # ------------------------------------------------------------------

    def move_to(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        speed: float = 6000.0,
        wait: bool = True,
        **extra_axes: float,
    ) -> None:
        """Move to absolute position. Omit any axis to leave it unchanged."""
        axes: dict[str, float] = {}
        if x is not None:
            axes["X"] = float(x)
        if y is not None:
            axes["Y"] = float(y)
        if z is not None:
            axes["Z"] = float(z)
        for k, v in extra_axes.items():
            axes[k.upper()] = float(v)
        if axes:
            self.driver.move_to(axes, s=speed, wait=wait)

    # ------------------------------------------------------------------
    # Relative motion (jogging)
    # ------------------------------------------------------------------

    def jog(
        self,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        speed: float = 6000.0,
        wait: bool = True,
        **extra_axes: float,
    ) -> None:
        """Move by relative deltas."""
        axes: dict[str, float] = {}
        if x is not None:
            axes["X"] = float(x)
        if y is not None:
            axes["Y"] = float(y)
        if z is not None:
            axes["Z"] = float(z)
        for k, v in extra_axes.items():
            axes[k.upper()] = float(v)
        if axes:
            self.driver.move(axes, s=speed, wait=wait)

    # ------------------------------------------------------------------
    # Homing
    # ------------------------------------------------------------------

    def home_all(self) -> None:
        """Home all axes."""
        self.driver.home_all()

    def home(self, *axes: Union[str, Enum]) -> None:
        """Home one or more axes sequentially."""
        for axis in axes:
            self.driver.home(axis)

    # ------------------------------------------------------------------
    # Tool management
    # ------------------------------------------------------------------

    def tool_lock(self) -> None:
        self.tool_changer.tool_lock()

    def tool_unlock(self) -> None:
        self.tool_changer.tool_unlock()

    def pickup_tool(self, tool: Union[int, Tool]) -> bool:
        """Pick up a tool by index or Tool instance."""
        index = tool.index if isinstance(tool, Tool) else int(tool)
        return self.tool_changer.pickup_tool(index)

    def park_tool(self) -> bool:
        """Park (deselect) the currently active tool."""
        return self.tool_changer.park_tool()

    # ------------------------------------------------------------------
    # Convenience info
    # ------------------------------------------------------------------

    def get_position(self) -> dict[str, float]:
        """Return the current axis positions."""
        return self.driver.get_positions()

    def get_active_tool(self) -> int:
        """Return the index of the currently active tool, or -1 if none."""
        return self.tool_changer.get_active_tool_index()

    def list_tools(self) -> dict:
        """Return a mapping of tool number -> info."""
        return self.tool_changer.get_tools()

    def get_available_axes(self) -> list[str]:
        """Return the list of axis letters available on this machine."""
        return self.driver.get_available_axes()
