import os
import shutil
import sys
import cv2
import numpy as np
import requests

from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT / "src"
PACKAGE_ROOT = SRC_ROOT / "science_jubilee"
DETECTOR_ROOT = PACKAGE_ROOT / "Horizontal_leafs_detector"

for path in (SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from science_jubilee.tools.Observer import Camera

# ==========================================================
# CONFIGURATION
# ==========================================================

OCTOPI_IP = "10.0.9.55"


def capture_photos():

    cam = Camera()
    a=True
    while a:
        try :

            confirmation= input("bougez la camera vers une nouvelle position et rentrez y / n pour annuler  ")
            cam.save_image()

            if confirmation.lower() != 'y':
                print("annulation")
                a= False
                return

        except KeyboardInterrupt:
            print("\nOpération annulée par l'utilisateur.")
            return



capture_photos()