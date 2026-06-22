import os
import cv2
import numpy as np
import requests
import time

from datetime import datetime
from pathlib import Path


# ==========================================================
# CONFIGURATION
# ==========================================================

OCTOPI_IP = "10.0.9.55"

LED_SERVER = "http://10.0.9.55:5000"

RAW_DATASET_DIR = Path("dataset_brut")
RAW_LED_DIR = Path("dataset_brut_led")
CLEAN_DATASET_DIR = Path("dataset_clean")
SEG_DATASET_DIR = Path("dataset_seg")

RAW_DATASET_DIR.mkdir(exist_ok=True)
RAW_LED_DIR.mkdir(exist_ok=True)
CLEAN_DATASET_DIR.mkdir(exist_ok=True)
SEG_DATASET_DIR.mkdir(exist_ok=True)


class Camera:

    offset_x = 4
    offset_y = 4

    # ======================================================
    # Capture image
    # ======================================================

    @staticmethod
    def capture_octopi_image(save_dir=RAW_DATASET_DIR,
                             url=f"http://{OCTOPI_IP}/webcam/?action=snapshot"):
        """
        Capture une image depuis OctoPi.
        """

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        output_file = save_dir / f"{timestamp}.jpg"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                with open(output_file, "wb") as f:
                    f.write(response.content)

                print(f"Image enregistrée : {output_file}")
                return output_file

            print(f"Erreur HTTP : {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"Erreur connexion : {e}")

        return None

    # ======================================================
    # Acquisition multi-éclairage
    # ======================================================

    def image_sans_ombre(self):
        # nettoyage du dossier temporaire
        for file in RAW_LED_DIR.glob("*.jpg"):
            file.unlink()

        # acquisition des 8 images
        for i in range(8):
            print(f"LED {i}")
            requests.get(f"{LED_SERVER}/pixel/{i}/255/255/255")
            time.sleep(0.5)

            self.capture_octopi_image(save_dir=RAW_LED_DIR)

            requests.get(f"{LED_SERVER}/pixel/{i}/0/0/0")
            time.sleep(0.2)

        return self.generate_minimum_image()

    # ======================================================
    # Génération image minimum
    # ======================================================

    def generate_minimum_image(self):
        image_files = sorted(RAW_LED_DIR.glob("*.jpg"))

        if len(image_files) == 0:
            raise ValueError("Aucune image dans dataset_brut_led")

        images = []

        for file in image_files:
            img = cv2.imread(str(file))
            if img is not None:
                images.append(img)

        result = images[0].copy()

        for img in images[1:]:
            result = np.minimum(result, img)

        output_file = (CLEAN_DATASET_DIR /f"{datetime.now():%Y%m%d_%H%M%S}.jpg")
        cv2.imwrite(str(output_file),result)

        print(f"Image sans reflet enregistrée : {output_file}")

        return output_file

    # ======================================================
    # Recherche image la plus récente
    # ======================================================

    @staticmethod
    def get_latest_image(folder=CLEAN_DATASET_DIR):
        files = list(folder.glob("*.jpg"))
        if len(files) == 0:
            raise FileNotFoundError(f"Aucune image dans {folder}")

        return max(files,key=os.path.getmtime)

    # ======================================================
    # Segmentation ExG
    # ======================================================

    def get_img_contour(self,img,
                        min_area_px=100,
                        max_area_px=5000,
                        min_circularity=0.4):

        b, g, r = cv2.split(img)
        exg = (
            2 * g.astype(np.int16)
            - r.astype(np.int16)
            - b.astype(np.int16))

        exg = cv2.normalize(exg,None,0,255,cv2.NORM_MINMAX)
        exg = exg.astype(np.uint8)

        _, mask = cv2.threshold(exg,0,255,cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask,cv2.MORPH_OPEN,kernel)
        mask = cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel)

        contours, _ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)

        valid_contours = []

        for cnt in contours:
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

            valid_contours.append(cnt)

        # sauvegarde debug segmentation
        seg_img = np.zeros(img.shape[:2],dtype=np.uint8)

        cv2.drawContours(seg_img,valid_contours,-1,255,-1)

        seg_file = (SEG_DATASET_DIR /f"{datetime.now():%Y%m%d_%H%M%S}.png")
        cv2.imwrite(str(seg_file),seg_img)

        return valid_contours

    # ======================================================
    # Détection lentille isolée
    # ======================================================
    #si la distance minimale d'isolation ne fonctionne pour aucune lentille
    #ajouter un cas ou l'on prend juste la plus éloignés
    def detect_isolated_duckweed(self,
                                 isolation_distance_px=100,
                                 min_area_px=100,
                                 max_area_px=5000,
                                 min_circularity=0.4,
                                 debug=False):
        """
        Retourne la première lentille isolée trouvée.
        """

        img_path = self.get_latest_image(CLEAN_DATASET_DIR)
        img = cv2.imread(str(img_path))

        if img is None:
            raise ValueError("Impossible de charger l'image")

        contours = self.get_img_contour(img,min_area_px,max_area_px,min_circularity)
        if len(contours) < 2:
            return None

        centers = []
        for cnt in contours:

            M = cv2.moments(cnt)
            if M["m00"] == 0:
                continue

            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            centers.append((cx, cy))

        for i, center in enumerate(centers):
            min_dist = np.inf

            for j, other in enumerate(centers):
                if i == j:
                    continue

                dist = np.linalg.norm(np.array(center)- np.array(other))

                min_dist = min(min_dist,dist)

            if min_dist > isolation_distance_px:
                if debug:
                    print(f"Lentille isolée trouvée : "f"{center}")

                return self.get_coordinate_from_pixel(center)

        return None

    # ======================================================
    # Conversion pixel -> repère plateau
    # ======================================================

    def get_coordinate_from_pixel(self,pos_px) -> tuple:

        """
        Fonction à calibrer expérimentalement.

        Retour :
        (x_mm, y_mm)
        """

        # --------------------------------------------------
        # Exemple :
        # diamètre réel du puits = 35 mm
        # diamètre observé = 600 px
        # --------------------------------------------------
        mm_per_pixel = 35 / 600
        center_well_px = (640,480)

        x_mm = (pos_px[0] - center_well_px[0]) * mm_per_pixel
        y_mm = (pos_px[1] - center_well_px[1]) * mm_per_pixel

        x_mm += self.offset_x
        y_mm += self.offset_y

        return (round(x_mm, 3),round(y_mm, 3))