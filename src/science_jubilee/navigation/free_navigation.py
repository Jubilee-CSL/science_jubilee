from __future__ import annotations

from typing import Optional, Union
from enum import Enum

from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.hal.tool_changer import ToolChanger
from science_jubilee.tools.Tool import Tool


class FreeNavigator:
    """Free-form motion controller built on MotionDriver.

    Unlike DeckNavigator, this class has no concept of a deck layout or
    labware geometry. It is useful for:
    - interactive setup and calibration workflows
    - jogging individual axes by relative increments
    - moving to arbitrary absolute positions
    - tool pickup and parking during setup

    All calls go through MotionDriver or ToolChanger; the transport is an
    implementation detail that FreeNavigator never touches directly.

    Parameters
    ----------
    driver:
        A fully initialised MotionDriver instance.
    tool_changer:
        A ToolChanger instance built on the same transport.

    Example
    -------
    >>> from science_jubilee.hal.transport.http import HTTPTransport
    >>> from science_jubilee.hal.motion_driver import MotionDriver
    >>> from science_jubilee.hal.tool_changer import ToolChanger
    >>> from science_jubilee.navigation.free_navigation import FreeNavigator
    >>>
    >>> transport = HTTPTransport(address="10.0.3.48")
    >>> driver = MotionDriver(transport)
    >>> tc = ToolChanger(transport)
    >>> nav = FreeNavigator(driver, tc)
    >>>
    >>> nav.move_to(x=150, y=150)
    >>> nav.jog(x=5)
    >>> nav.pickup_tool(0)
    >>> nav.park_tool()
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
        """Move to an absolute position on any combination of axes.

        Parameters
        ----------
        x, y, z:
            Target positions in mm for those axes. Omit any axis to leave
            it unchanged.
        speed:
            Feedrate in mm/min.
        wait:
            Block until motion is complete.
        **extra_axes:
            Any additional axes by single-letter keyword, e.g. ``u=30``.
        """
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
        """Move relative to the current position (jog) on any axes.

        Parameters
        ----------
        x, y, z:
            Delta in mm to add to the current position.
        speed:
            Feedrate in mm/min.
        wait:
            Block until motion is complete.
        **extra_axes:
            Any additional axes by single-letter keyword, e.g. ``u=-2``.
        """
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
        """Home all axes by running the Duet's ``homeall.g`` macro.

        Delegates to ``M98 P"homeall.g"`` so the firmware's own homing
        sequence is used (U first to release any active tool, then Y, X, Z).
        This is equivalent to pressing *Home All* in DWC.

        Example
        -------
        >>> nav.home_all()
        """
        self.driver.home_all()

    def home(self, *axes: Union[str, Enum]) -> None:
        """Home one or more specific axes sequentially.

        Parameters
        ----------
        *axes:
            Axis letters (str), e.g. ``'X'``.

        Example
        -------
        >>> nav.home("x", "y")     # home X then Y only
        >>> nav.home("z")
        """
        for axis in axes:
            self.driver.home(axis)

    # ------------------------------------------------------------------
    # Tool management
    # ------------------------------------------------------------------

    def tool_lock(self) -> None:
        """Engage the toolchanger lock by running the tool_lock macro.

        Use this during manual setup after physically placing a tool against
        the carriage — it engages the U-axis lock without triggering a full
        tool-change sequence.

        Example
        -------
        >>> nav.tool_lock()
        """
        self.tool_changer.tool_lock()

    def tool_unlock(self) -> None:
        """Disengage the toolchanger lock by running the tool_unlock macro."""
        self.tool_changer.tool_unlock()

    def pickup_tool(self, tool: Union[int, Tool]) -> bool:
        """Pick up a tool via the full RRF tool-change sequence (T{n}).

        Sends ``T{n}`` which causes RepRapFirmware to automatically run:
          1. ``tfree{current}.g`` — park the currently active tool (if any)
          2. ``tpre{n}.g``        — approach the target parking post
          3. ``tpost{n}.g``       — lock the tool and restore position

        Parameters
        ----------
        tool:
            Either an integer tool index or a Tool instance.

        Returns
        -------
        bool
            True if the command was sent successfully.

        Example
        -------
        >>> nav.pickup_tool(0)
        >>> nav.pickup_tool(my_tool)
        """
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
