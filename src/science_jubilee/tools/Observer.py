import logging
import os
import time

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.hal.tool_changer import ToolChanger


import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)


# ==========================================================
# CONFIGURATION
# ==========================================================

RAW_DATASET_DIR = Path("dataset_brut")
RAW_LED_DIR = Path("dataset_brut_led")

RAW_DATASET_DIR.mkdir(exist_ok=True)
RAW_LED_DIR.mkdir(exist_ok=True)
@dataclass
class Neopixel:
    url: str

    def pixel_on(self, led_index, r, g, b):
        requests.get(f"{self.url}/pixel/{led_index}/{r}/{g}/{b}")

    def pixel_off(self, led_index):
        requests.get(f"{self.url}/pixel/{led_index}/0/0/0")

    def all_pixel_on(self, r, g, b):
        requests.get(f"{self.url}/led/{r}/{g}/{b}")

    def all_pixel_off(self):
        requests.get(f"{self.url}/off")


class Camera:
    
    def __init__(self, motion, tool_changer, address: str, led_address: Optional[str] = None):
        self.driver : MotionDriver= motion
        self.tool_changer : ToolChanger = tool_changer

        self.leds: Optional[Neopixel] = Neopixel(url=f"http://{led_address}:5001") if led_address else None

        self.K = np.array([
        [1223.5800404310712, 0, 1012.6265109062106],
        [0, 1234.9709223262516, 652.0441120068181],
        [0, 0, 1]], dtype=np.float64)

        # Remplacer par les coefficients issus de la calibration
        self.dist = np.array([0.003964559927730257,
                     -0.07805139087827796,
                     0.000522562108766698,
                     -0.000680263815167156,
                     0.26622436928189075])
        
        # Pose de la caméra dans le repère machine
        self.R_machine_camera = np.array([[1, 0, 0],
                                        [0, 1, 0],
                                        [0, 0, 1]])
        
        self.url = f"http://{address}/webcam/?action=snapshot"
        
        self.offset = (0,-20,0)   ##offset utilisé par quentin
        #self.offset =(-5,0,10) # dernier offset marigold
        #self.offset=(10,-13,16)
        self.T_machine_camera = np.array([0,0,0], dtype=np.float64)
        
    # ======================================================
    # Capture image
    # ======================================================
    def move_to_get_image(self,x_depart,y_depart,z_depart):

        
        active_tool = self.tool_changer.get_active_tool_index()

        if active_tool == -1:
           active_tool_offset = (0,0,0)

        active_tool_offset = self.tool_changer.get_tool_offset(active_tool)

        x = x_depart+ active_tool_offset[0] 
        y =y_depart+ active_tool_offset[1] 
        z = z_depart + active_tool_offset[2]
        self.driver.move_to({"Z":float(z)},s=600)
        self.driver.move_to({"X":float(x),
                          "Y":float(y),}, s=800)
        
        position = self.driver.get_positions()

        self.T_machine_camera = np.array([position["X"] - active_tool_offset[0] - self.offset[0],
                                          position["Y"] - active_tool_offset[1] - self.offset[1],
                                          -position["Z"] - active_tool_offset[2] - self.offset[2]], dtype=np.float64)

    def get_image(self) -> np.ndarray:
        """Capture une image depuis OctoPi."""

        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()

            img = cv2.imdecode(
                np.frombuffer(response.content, np.uint8),
                cv2.IMREAD_COLOR,
            )

            if img is None:
                raise RuntimeError("Impossible de décoder l'image.")
            
            return img

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Erreur connexion caméra : {e}")

    def save_image(self, img=None, save_dir=RAW_DATASET_DIR, save_name=None):

        if img is None:
            img = self.get_image()

        if save_name is None:
            save_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

        output_file = save_dir / f"{save_name}.jpg"

        cv2.imwrite(str(output_file), img)

    # ======================================================
    # Acquisition multi-éclairage
    # ======================================================

    def get_multi_lighting_img(
        self,
        nb_img=8,
        temp_dir=RAW_LED_DIR,
    ):
        # on s'assure que tout soit éteint
        if self.leds is None:
            raise RuntimeError("Neopixel not configured; set JUBILEE_NEOPIXEL_ADDRESS.")
        self.leds.all_pixel_off()

        # nettoyage du dossier temporaire
        for file in temp_dir.glob("*.jpg"):
            file.unlink()

        images = []
        # acquisition des images
        for i in range(nb_img):
            logger.debug("LED %d", i % nb_img)
            self.leds.pixel_on(i % nb_img, 255, 255, 50)
            time.sleep(3)

            images.append(self.get_image())
            self.save_image(img=images[i], save_dir=temp_dir)

            self.leds.pixel_off(i)
            time.sleep(0.2)

        return images

    # ======================================================
    # Génération image minimum
    # ======================================================

    def get_clean_image(
        self, images=None, save_dir=None, save_name=None, nb_image_used=8
    ):

        if images is None:
            images = self.get_multi_lighting_img(nb_img=nb_image_used)

        if len(images) == 0:
            raise ValueError("Aucune image")

        result = images[0].copy()

        for img in images[1:]:
            result = np.minimum(result, img)

        if save_dir != None:
            if save_name == None:
                self.save_image(
                    img=result,
                    save_dir=save_dir,
                )
            else:
                self.save_image(img=result, save_dir=save_dir, save_name=save_name)

        return result
