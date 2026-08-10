from dataclasses import dataclass

from science_jubilee.navigation.free_navigation import FreeNavigator
from science_jubilee.tools.Tool import Tool, requires_active_tool


@dataclass(slots=True, repr=False)
class Pen(Tool):
    """A class representation of an inoculator.

    :param Tool: The base tool class
    :type Tool: :class:`Tool`
    """

    @requires_active_tool
    def draw_line(
        self,
        nav: FreeNavigator,
        axis=0,
        x=None,
        y=None,
        lenght=10,
        speed_z=1000,
        speed_draw=1000,
    ) -> None:
        """
        Draws a straight line with the pen tool, from a start point to an end point, axis 0 is for 'x' and 1 for 'y'
        """
        pose = nav.get_position()
        if x == None and y == None:
            x = pose[0]
            y = pose[1]
        nav.move_to(x=x, y=y, z=0, speed=speed_z)
        nav.jog(lenght)
        nav.move_to(z=pose[2], speed=3000)

    def draw_rectangle(self, nav: FreeNavigator, center, width, lenght):
        "Draws a square thanks to its center, the wide is along x axis and y along y"
        nav.move_to(x=center - width / 2, y=center - width / 2, speed=1000)
        nav.move_to(z=0, speed=1000)
        nav.jog(x=width, speed=500)
        nav.jog(y=lenght, speed=500)
        nav.jog(x=-width, speed=500)
        nav.jog(y=-lenght, speed=500)
        nav.move_to(z=200, speed=1000)

    def draw_deck(self, nav: FreeNavigator, labware_dic):
        """
        This uses the Science_jubilee_interface, experience json output, to draw the labware emplacements, precisely
        """
        for slot in labware_dic["slots"]:
            if slot["shape"] == "rectangle":
                self.draw_rectangle(
                    nav, slot["coordinates"], slot["width"], slot["length"]
                )
