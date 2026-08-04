import os
import shutil
import sys
import cv2
import numpy as np
import requests
import time
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_ROOT = REPO_ROOT
PACKAGE_ROOT = SRC_ROOT / "science_jubilee/Vision"
DETECTOR_ROOT = PACKAGE_ROOT / "Marigold_Horizontal_leafs"

for path in (SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

from science_jubilee.tools.Observer import Camera
from science_jubilee.Vision.Marigold_Horizontal_leafs.src import segment_and_target
from science_jubilee.hal.transport.http import HTTPTransport
from science_jubilee.hal.transport.mock import MockTransport
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.navigation.free_navigation import FreeNavigator
from science_jubilee.hal.tool_changer import ToolChanger

# ==========================================================
# CONFIGURATION
# ==========================================================

transport = HTTPTransport(address="10.0.9.6")
#transport = MockTransport()  # Utiliser le transport mock pour les tests sans matériel réel
driver = MotionDriver(transport)
tool_changer = ToolChanger(transport)
nav = FreeNavigator(driver, tool_changer)
OCTOPI_IP = "10.0.9.55"
target_auto=True  # True pour sélectionner automatiquement le target avec la plus grande surface et la plus proche distance de la caméra, False pour demander confirmation à l'utilisateur
#coordonées de départ(sans le offset de l'outil)
x_depart=142.0
y_depart=155.0
z_depart=320
def deck_clear():
    return True

def main():
     # se mettre au millieu pour prendre la photo
    transport.deck_clear_provider= deck_clear
    tool_changer.pickup_tool(0) 

    #on veut que la camera se place à cet emplacement donc on enleve l'offset de l'outil pour revenir à l'offset global
    time.sleep(2)
    camera = Camera(motion=driver,tool_changer=tool_changer)
    camera.move_to_get_image(x_depart,y_depart,z_depart)
    # ======================================================
    # RECHERCHE IMAGE LA PLUS RECENTE
    # ======================================================
    images_dir = DETECTOR_ROOT / "input"
    images_dir.mkdir(exist_ok=True)
    img = camera.get_image()
    cv2.imwrite(str(images_dir / "latest.jpg"), img)
    output_dir = DETECTOR_ROOT / "output"/ "latest"
    output_dir.mkdir(exist_ok=True)



    # ======================================================
    # Réaliser la detection des surfaces horizontales 
    # ====================================================== 
    targets = segment_and_target.run_pipeline(image_path=images_dir / "latest.jpg", output_dir=output_dir, config_path=DETECTOR_ROOT /"config.yaml", use_ai=True)
    while len(targets)==0:
        print("Aucune surface detectée, relance du modèle, appuyez Ctrl+c pour quitter")
        targets = segment_and_target.run_pipeline(image_path=images_dir / "latest.jpg", output_dir=output_dir, config_path=DETECTOR_ROOT /"config.yaml", use_ai=True)
    print(f"Targets detected: {len(targets)}, veuillez vérifier le fichier output/targets.json pour plus de détails.")
    if target_auto == False:
        print("Veuillez sélectionner un target parmi les suivants:")
        for i, target in enumerate(targets):
            print(f"{i}: {target}")
        try:
            selected_index = int(input("Entrez l'index du target souhaité: "))
            while selected_index < 0 or selected_index >= len(targets):
                print("Index invalide. Veuillez réessayer.")
                selected_index = int(input("Entrez l'index du target souhaité: "))
            target = targets[selected_index]
        except ValueError:
            print("Entrée invalide. Veuillez entrer un nombre entier.")
            return
        except KeyboardInterrupt:
            print("\nOpération annulée par l'utilisateur.")
            return
    else:
        #On prend le target avec la plus grande surface et la plus plus proche distance de la caméra
        #target = max(targets, key=lambda x: (x['area_px'], -x['xyz_mm'][2]))  # On maximise le score et minimise la distance
        target = max(targets, key=lambda x: ( -x['xyz_mm'][2])) 
    """
    print(f"Target choisi: {target}, veuillez confirmer que c'est bien la cible souhaitée.")
    
    try:
        confirmation = input("Confirmez-vous ce target? (y/n): ")
        if confirmation.lower() != 'y':
            print("Cible non confirmée. Veuillez sélectionner une autre cible.")
            return
    except KeyboardInterrupt:
        print("\nOpération annulée par l'utilisateur.")
        return
    """

    offset_x =  camera.offset[0]  # Offset en mm pour ajuster la position finale sur l'axe X
    offset_y =  camera.offset[1]  # Offset en mm pour ajuster la position finale sur l'axe Y
    offset_z =  camera.offset[2]  # Offset en mm pour ajuster la position finale sur l'axe Z

    # ======================================================
    # On bouge vers le target
    # ======================================================
    # On se déplace vers le target en gardant la même hauteur

    nav.move_to(x=x_depart + target['xyz_mm'][0] + offset_x, y= y_depart -target['xyz_mm'][1] + offset_y, speed=3000.0, wait=True)  
    nav.move_to(z=z_depart + offset_z -target['xyz_mm'][2] -5, speed=1000.0, wait=True)  

if __name__ == "__main__":
    main()