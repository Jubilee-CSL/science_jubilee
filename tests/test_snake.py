

import logging
import pytest

from science_jubilee.navigation.free_navigation import FreeNavigator
import time

logger = logging.getLogger(__name__)

#Utiliser ce test pour réaliser des photos et dataset

@pytest.mark.invasive
def test_capture_snake(motion, tool_changer, camera):
    freenav = FreeNavigator(motion, tool_changer)
    cam = camera
    time.sleep(10)
    cam.save_image()
    """
    freenav.move_to(z = 320)
    start_point_x = 144
    start_point_y=125
    jogging = 2
    #point de départ en 10 10 320
    #point d'arrivée visé 310 310 320
    freenav.move_to(x = start_point_x, y = start_point_y)
    for i in range(20):
        for y in range(10):
            time.sleep(2)
            cam.save_image()
            freenav.jog(y = jogging)
        freenav.move_to(y = start_point_y)
        freenav.jog(x= jogging)
      
    """
        