

import logging
import pytest

from science_jubilee.navigation.free_navigation import FreeNavigator
from science_jubilee.tools.Observer import Camera
import time

logger = logging.getLogger(__name__)

#Utiliser ce test pour réaliser des photos et dataset

@pytest.mark.invasive
def test_capture_snake(motion,tool_changer):
    freenav = FreeNavigator(motion,tool_changer)
    cam = Camera(motion,tool_changer)
    freenav.move_to(z = 320)
    start_point = 60
    jogging = 20
    #point de départ en 10 10 320
    #point d'arrivée visé 310 310 320
    freenav.move_to(x = start_point, y = start_point)
    for i in range(10):
        for y in range(10):
            time.sleep(2)
            cam.save_image()
            freenav.jog(y = jogging)
        freenav.move_to(y = start_point)
        freenav.jog(x= jogging)
      

        