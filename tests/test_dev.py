import requests
import subprocess

import logging
import os

import pytest

from science_jubilee.tools.Observer import Camera
import time

"""
subprocess.run([
    "ssh",
    "jubilee@10.0.9.55",
    "python3 /home/pi/led_server.py"
])

requests.get(
    "http://10.0.9.55:5001/pixel/4/255/255/255"
)
"""

logger = logging.getLogger(__name__)


@pytest.mark.invasive
def capture_snake(motion):
    cam = Camera
    motion.move_to(z = 320)
    #point de départ en 10 10 320
    #point d'arrivée visé 310 310 320
    motion.move_to(x = 10, y = 10)
    for i in range(10):
        for y in range(10):
            motion.move(y = 30)
        motion.move_to(y = 10)
        motion.move(x= 30)
        time.sleep(5)
        cam.capture_octopi_image()

        
