import os, shutil
import cv2
import numpy as np
import requests

from datetime import datetime
from pathlib import Path

from cellpose import models, core

# ==========================================================
# CONFIGURATION
# ==========================================================

OCTOPI_IP = "10.0.9.55"

RAW_DATASET_DIR = Path("dataset_brut")
SEG_DATASET_DIR = Path("dataset_seg")

RAW_DATASET_DIR.mkdir(exist_ok=True)
SEG_DATASET_DIR.mkdir(exist_ok=True)

class Camera:
    
    use_GPU = core.use_gpu()
    yn = ['NO','Yes']
    print(f'>>>GPU activated?{yn[use_GPU]}')

    @staticmethod
    def capture_octopi_image(url=f"http://{OCTOPI_IP}/webcam/?action=snapshot",):
        """
        Capture une image et l'enregistre dans dataset_brut.
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = RAW_DATASET_DIR / f"{timestamp}.jpg"

        try:
            print("Connexion à OctoPi...")
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                with open(output_file, "wb") as f:
                    f.write(response.content)
                print(f"Image enregistrée : {output_file}")
                return str(output_file)

            print(f"Erreur HTTP : {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"Erreur connexion : {e}")

        return None

    # ======================================================
    # RECHERCHE IMAGE LA PLUS RECENTE
    # ======================================================

    @staticmethod
    def get_latest_image():
        files = list(RAW_DATASET_DIR.glob("*.jpg"))

        if len(files) == 0:
            raise FileNotFoundError("Aucune image dans dataset_brut")
        
        return max(files, key=os.path.getmtime)

    # ======================================================
    # SEGMENTATION CELLPOSE
    # ======================================================

    @staticmethod
    def segment_latest_image(model_type="cpsam",diameter=None,flow_threshold=0.4,cellprob_threshold=0.0):
        """
        Segmente l'image la plus récente avec Cellpose.
        """
        image_path = Camera.get_latest_image()
        img = cv2.imread(str(image_path))

        if img is None:
            raise ValueError("Impossible de charger l'image")

        print("Chargement du modèle Cellpose...")
        model = models.CellposeModel(gpu= True,model_type=model_type)

        #Segmente la liste d'image ou l'image passé en paramètre
        masks, flows, styles, diams = model.eval(
            img,
            diameter=diameter,
            channels=[0, 0],
            flow_threshold=flow_threshold,
            cellprob_threshold=cellprob_threshold
        ) 

        mask_visu = (masks.astype(np.float32)/ masks.max()* 255).astype(np.uint8)
        output_name = (image_path.stem + "_seg.png")
        output_path = SEG_DATASET_DIR / output_name

        cv2.imwrite(str(output_path),mask_visu)
        print(f"Segmentation sauvegardée : {output_path}")

        return masks, output_path

    # ======================================================
    # DETECTION LENTILLES ISOLEES
    # ======================================================

    @staticmethod
    def detect_isolated_duckweed(
        masks,
        min_area_px=100,
        max_area_px=5000,
        min_circularity=0.4,
        isolation_distance_px=100,
        debug=False
    ):
        """
        Détection de lentilles isolées.

        Paramètres :
        ------------
        min_area_px :       surface minimale d'une lentille
        max_area_px :       surface maximale
        min_circularity :   filtre forme

        isolation_distance_px :     distance minimale avec le voisin le plus proche

        Retour : list
        """

        isolated_duckweeds = []
        labels = np.unique(masks)
        labels = labels[labels > 0]

        centroids = []
        objects = []
        
        #Partie de la fonction a grandement retravaillé, utilisé pour compenser les potentiels erreurs du modèle 
        #A terme le modèle devra être suffisament entrainé pour ne pas avoir besoin de ces corrections, min max min_circularity

        for label in labels:
            obj_mask = (masks == label).astype(np.uint8)

            contours, _ = cv2.findContours(obj_mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

            if len(contours) == 0:
                continue

            cnt = contours[0]
            area = cv2.contourArea(cnt)

            if area < min_area_px:
                continue
            if area > max_area_px:
                continue

            perimeter = cv2.arcLength(cnt,True)

            if perimeter == 0:
                continue

            circularity = (4* np.pi* area/ (perimeter ** 2))

            if circularity < min_circularity:
                continue

            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue
            
            #les valeurs récupérer sont en pixels 
            #ils sera insdispensables de les transformé en coordonnées dans le réferentiel du plateau par un calcul
            #qui prend en compte la hauteur a laquelle l'image est prise 
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])

            centroids.append((cx, cy))

            objects.append(
                {
                    "label": label,
                    "area": area,
                    "circularity": circularity,
                    "center": (cx, cy)
                }
            )

        # =====================================
        # Calcul isolement
        # =====================================
        # A terme il sera préferable de rechercher la duckweed la plus éloignés 
        # ou pour gagner du temps la première duckweed suffisament éloignés
        #plutot que toutes les duckweeds éloignés d'une distance paramétrisée
        for i, obj in enumerate(objects):
            current_center = np.array(obj["center"])
            min_dist = np.inf

            for j, other in enumerate(objects):
                if i == j:
                    continue
                d = np.linalg.norm(current_center - np.array(other["center"]))

                min_dist = min(min_dist, d)

            if min_dist > isolation_distance_px:
                obj["nearest_distance"] = min_dist
                isolated_duckweeds.append(obj)

        if debug:
            print(f"Lentilles isolées : "f"{len(isolated_duckweeds)}")

        return isolated_duckweeds


