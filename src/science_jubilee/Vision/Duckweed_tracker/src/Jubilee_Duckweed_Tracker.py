import logging
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT

for path in (SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import duckweed_segment_and_track
import numpy as np
import yaml

from science_jubilee.decks.Deck import Deck
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.hal.tool_changer import ToolChanger
from science_jubilee.hal.transport.http import HTTPTransport
from science_jubilee.labware.Labware import Well
from science_jubilee.navigation.deck_navigation import DeckNavigator
from science_jubilee.tools.camera.toolheadcam import ToolheadCam

LED_SERVER = "http://10.0.9.55:5001"

logger = logging.getLogger(__name__)

# Test à utiliser uniquement en Hardware
transport = HTTPTransport(address="10.0.9.6")
driver = MotionDriver(transport)
tool_changer = ToolChanger(transport)
deck = Deck(os.getenv("JUBILEE_DECK_DEF", "lab_automation_deck_AFL_bolton.json"))
nav = DeckNavigator(driver, deck=deck)
"""
intrinsics= REPO_ROOT/ "science_jubilee/Vision/Camera_calibration/src/camera_params.yaml"
with open(intrinsics, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            intrinsics= loaded["camera"]
"""
offest_sup = (-10,10,18) #supplementary offset spécific to the selected tool
def deck_clear():
    return True

def main(debug,x_depart=142.0,y_depart=155.0, z_depart= 186.0, well = None, use_ai=False):
    #requests.get(f"{LED_SERVER}/led/255/255/255")
    transport.deck_clear_provider= deck_clear
    cam = ToolheadCam(motion=driver, tool_changer=tool_changer,address="10.0.9.55",calib_file=REPO_ROOT/ "science_jubilee/calibration/camera_params.yaml")
    #cam.K=  np.array([   [intrinsics["fx"], 0, intrinsics["cx"]],  [0, intrinsics["fy"], intrinsics["cy"]],    [0, 0, 1]  ], dtype=np.float32)
        #Improvement of the model by including the distortion parameters given py the opencv calibration
    
    #cam.dist = np.array(intrinsics["dist"], dtype=np.float32)
    tool_changer.pickup_tool(0)
    np.array(tool_changer.get_tool_offset(0))
    print(cam.offset)
    print(tool_changer.get_tool_offset(0))

    cam.move_to_get_image(x_depart, y_depart, z_depart)
    time.sleep(3)
    img = cam.get_image()
    img1 = img.copy()
    # img = cam.get_latest_image(folder = Path("dataset_brut"))
    duckweed, float_center, checkpoints = duckweed_segment_and_track.main(
        img=img1, camera=cam, float_radius_mm=37.5, use_AI=use_ai
    )
    print(
        f"Target choisi: {duckweed}, veuillez confirmer que c'est bien la cible souhaitée."
    )
    if well == None:
        well = Well(
        "A1",
        depth=120,
        totalLiquidVolume=80,
        shape="circular",
        x=float(x_depart + cam.offset[0] + float_center[0]+offest_sup[0]),
        y=float(y_depart + cam.offset[1] - float_center[1]+offest_sup[1]),
        z=2,
        diameter=37.5*2,
        )
    else:
        error = np.linalg.norm(np.array(well.x, well.y) - float_center)
        print(f"Erreur de détéction du puit à {error} mm ")

    x_goal = float(x_depart + cam.offset[0] + duckweed[0]+offest_sup[0])
    y_goal = float(y_depart + cam.offset[1] - duckweed[1]+offest_sup[1])
    z_goal = float(z_depart+cam.offset[2]-duckweed[2] +offest_sup[2] )   
     
    print(f"Target choisi: {x_goal,y_goal,z_goal}, veuillez confirmer que c'est bien la cible souhaitée.")
    if debug == True:
        try:
            confirmation = input("Confirmez-vous ce target? (y/n): ")
            if confirmation.lower() != "y":
                print("Cible non confirmée. Veuillez sélectionner une autre cible.")
                return
        except KeyboardInterrupt:
                print("\nOpération annulée par l'utilisateur.")
                return
    logger.info("x = %s, y= %s, z= %s",x_goal,y_goal,z_goal)
    nav.move_to_well(well,speed_xy=500,speed_z=200)
    
    # Try planning a path of checkpoints inside the well and execute it
    
    clipped_checkpoints = []
    for x, y ,z in checkpoints:
            x=x + x_depart + cam.offset[0]+offest_sup[0]
            y=-y + y_depart + cam.offset[1]+offest_sup[1]    
            clipped_checkpoints.append((x, y, z))

    if len(clipped_checkpoints) == 0:
            raise RuntimeError("No valid checkpoints generated")

        # 1) Move in XY to the RRT start point (first checkpoint)
    start_wx, start_wy, start_wz = clipped_checkpoints[0]
    dx_start = float(start_wx - well.x)
    dy_start = float(start_wy - well.y)
    nav.move_inside_well(well=well, dx=dx_start, dy=dy_start, speed_xy=400)

        # 2) Enter water: safe Z then approach Z
    nav.move_inside_well(well=well, z=z_goal + 17, speed_z=200)
    nav.move_inside_well(well=well, z=z_goal + 7, speed_z=50)

        # 3) Follow remaining checkpoints by XY moves only
    prev_wx, prev_wy, prev_wz = clipped_checkpoints[0]
    for wx, wy, wz in clipped_checkpoints[1:]:
            dx_step = float(wx - prev_wx)
            dy_step = float(wy - prev_wy)
            nav.move_inside_well(well=well, dx=dx_step, dy=dy_step, speed_xy=200)
            prev_wx, prev_wy, prev_wz = wx, wy, wz
    #petit cercle de recherche de 3 mm
    nav.move_inside_well(well=well,dx=1,speed_xy=50)
    nav.move_inside_well(well=well,dx=-1,dy=1,speed_xy=50)
    nav.move_inside_well(well=well,dy=-1,speed_xy=50)
    nav.move_inside_well(well=well,dx=-1,speed_xy=50)
    nav.move_inside_well(well=well,dx=1,dy=-1,speed_xy=50)
    nav.move_inside_well(well=well,dy=+1,speed_xy=50)
    
    
    nav.move_inside_well(well=well,z=z_goal+20,speed_z=200)
    nav.move_inside_well(well=well,z=z_goal+70,speed_z=800)
"""
#test transfert
    from science_jubilee.navigation.free_navigation import FreeNavigator
    freenav= FreeNavigator(driver,tool_changer=tool_changer)
    freenav.move_to(z=200,speed=1000)
    freenav.move_to(x=209.0,y=105.0,speed=4000)
    freenav.move_to(z=15.00,speed=2000)
    freenav.jog(x=+3,y=-3,speed=1000)
    freenav.move_to(z=200,speed=3000)
"""
if __name__ == "__main__":
    main(True)
