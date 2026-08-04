import time
from pathlib import Path
import sys
import pytest
import logging
import requests
import os

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT

for path in (SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from science_jubilee.tools.camera.toolheadcam import ToolheadCam
from science_jubilee.labware.Labware import Well
from science_jubilee.hal.tool_changer import ToolChanger
from science_jubilee.hal.transport.http import HTTPTransport
from science_jubilee.hal.transport.mock import MockTransport
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.navigation.deck_navigation import DeckNavigator
from science_jubilee.decks.Deck import Deck
import duckweed_segment_and_track
import numpy as np
import yaml
LED_SERVER = "http://10.0.9.55:5001"

logger = logging.getLogger(__name__)
 
#Test à utiliser uniquement en Hardware
transport= HTTPTransport(address="10.0.9.6")
driver = MotionDriver(transport)
tool_changer = ToolChanger(transport)
deck= Deck(os.getenv("JUBILEE_DECK_DEF", "lab_automation_deck_AFL_bolton.json"))
nav = DeckNavigator(driver, deck=deck)
intrinsics= REPO_ROOT/ "science_jubilee/Vision/Camera_calibration/src/camera_params.yaml"
with open(intrinsics, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            intrinsics= loaded["camera"]

def deck_clear():
    return True

def main(debug,x_depart=142.0,y_depart=155.0, z_depart= 200.0, well = None):
    #requests.get(f"{LED_SERVER}/led/255/255/255")
    transport.deck_clear_provider= deck_clear
    cam = Camera(motion=driver, tool_changer=tool_changer)
    cam.K=  np.array([
            [intrinsics["fx"], 0, intrinsics["cx"]],
            [0, intrinsics["fy"], intrinsics["cy"]],
            [0, 0, 1]
        ], dtype=np.float32)
        #Improvement of the model by including the distortion parameters given py the opencv calibration
    
    cam.dist = np.array(intrinsics["dist"], dtype=np.float32)
    tool_changer.pickup_tool(0)
    tool_offset = np.array(tool_changer.get_tool_offset(0))
    print(cam.offset)
    print(tool_changer.get_tool_offset(0))
    
    cam.move_to_get_image(x_depart,y_depart,z_depart)
    time.sleep(3)
    img = cam.get_image()
    img1 = img.copy()
    #img = cam.get_latest_image(folder = Path("dataset_brut"))
    duckweed, float_center = duckweed_segment_and_track.main(img=img1,camera=cam,float_radius_mm=37.5)
    print(f"Target choisi: {duckweed}, veuillez confirmer que c'est bien la cible souhaitée.")
    if well==None:
        well = Well(
        "A1",
        depth=70,
        totalLiquidVolume=80,
        shape="circular",
        x=float(x_depart + cam.offset[0] + float_center[0]),
        y=float(y_depart + cam.offset[1] - float_center[1]),
        z=2,
        diameter=37.5*2,
        )
    else :
        error = np.linalg.norm(np.array(well.x,well.y)-float_center)
        print(f"Erreur de détéction du puit à {error} mm ")
    

    x = float(x_depart + cam.offset[0] + duckweed[0])
    y = float(y_depart + cam.offset[1] - duckweed[1])
    z = float(z_depart+cam.offset[2]-duckweed[2]  )   
     
    print(f"Target choisi: {x,y,z}, veuillez confirmer que c'est bien la cible souhaitée.")
    if debug == True:
        try:
                confirmation = input("Confirmez-vous ce target? (y/n): ")
                if confirmation.lower() != 'y':
                    print("Cible non confirmée. Veuillez sélectionner une autre cible.")
                    return
        except KeyboardInterrupt:
                print("\nOpération annulée par l'utilisateur.")
                return
    logger.info("x = %s, y= %s, z= %s",x,y,z)
    dx , dy =  x - well.x ,  y - well.y
    nav.move_to_well(well,speed_xy=500,speed_z=700)
    
    nav.move_inside_well(well=well,dx=dx,dy=dy+8,speed_xy=600)
    nav.move_inside_well(well=well,z=z+17,speed_z=200)

    nav.move_inside_well(well=well,z=z+7,speed_z=50)
    nav.move_inside_well(well=well,dy=-6,speed_xy=200)
    #petit cercle de recherche de 3 mm
    nav.move_inside_well(well=well,dx=1,speed_xy=50)
    nav.move_inside_well(well=well,dx=-1,dy=1,speed_xy=50)
    nav.move_inside_well(well=well,dy=-1,speed_xy=50)
    nav.move_inside_well(well=well,dx=+1,dy=-1,speed_xy=50)
    
    
    nav.move_inside_well(well=well,z=z+20,speed_z=40)
    nav.move_inside_well(well=well,z=z+40,speed_z=800)

#test transfert
    from science_jubilee.navigation.free_navigation import FreeNavigator
    freenav= FreeNavigator(driver,tool_changer=tool_changer)
    freenav.move_to(z=200,speed=1000)
    freenav.move_to(x=209.0,y=105.0,speed=4000)
    freenav.move_to(z=15.00,speed=2000)
    freenav.jog(x=+3,y=-3,speed=1000)
    freenav.move_to(z=200,speed=3000)
if __name__ == "__main__":
    main(True)
