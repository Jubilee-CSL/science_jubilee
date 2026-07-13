
import time
from pathlib import Path

import pytest
import logging
import requests

from science_jubilee.tools.Observer import Camera

from science_jubilee.tools.Observer import Camera
from science_jubilee.labware.Labware import Well

LED_SERVER = "http://10.0.9.55:5001"

""" Test a utilisé uniquement en Hardware
@pytest.mark.invasive
def test_imag(motion, navigator, tool_changer):
    #requests.get(f"{LED_SERVER}/led/255/255/255")
    cam = Camera(motion, tool_changer)
    
    tool_changer.pickup_tool(0)
    well = Well("A1", depth=70,totalLiquidVolume=80,shape="circular",
                x=150, y=150, z= 2, diameter= 83)
    navigator.move_to_well(well)
    cam.move_to_get_image()
    time.sleep(3)
    img = cam.get_image()
    img1 = img.copy()
    #img = cam.get_latest_image(folder = Path("dataset_brut"))
    contour = cam.get_img_contour(img = img, debug=True)
    isolated_lens = cam.detect_isolated_duckweed(valid_contours= contour)
    logger.info(isolated_lens)

    float_points = cam.get_float_points(img=img1,debug=False)
    
    x,y,z = cam.get_lens_position(lens_pixel= isolated_lens,
                                  float_points=float_points,
                                  float_radius_mm=37.5)
    
    logger.info("x = %s, y= %s, z= %s",x,y,z)
    dx , dy =  x - well.x ,  y - well.y
    navigator.move_to_well(well)
    navigator.move_inside_well(well=well,dx=dx,dy=dy)
    navigator.move_inside_well(well=well,z=z+5,speed_z=500)

    navigator.move_inside_well(well=well,z=z,speed_z=100)
    navigator.move_inside_well(well=well,dx=5,speed_xy=500)



    navigator.move_to_safe_z()

"""
