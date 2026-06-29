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

LED_SERVER = "http://10.0.9.55:5001"

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
    url = f"http://{OCTOPI_IP}/webcam/?action=snapshot"

    # ======================================================
    # Capture image
    # ======================================================

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

    def get_multi_lighting_img(self, nb_img = 8, temp_dir = RAW_LED_DIR,):
        #on s'assure que tout soit éteint
        requests.get(f"{LED_SERVER}/off")

        # nettoyage du dossier temporaire
        for file in temp_dir.glob("*.jpg"):
            file.unlink()

        images = []
        # acquisition des images
        for i in range(nb_img):
            print(f"LED {i%nb_img}")
            requests.get(f"{LED_SERVER}/pixel/{i%nb_img}/255/255/50")
            time.sleep(3)

            images.append(self.get_image())
            self.save_image(img = images[i], save_dir=temp_dir)
            
            requests.get(f"{LED_SERVER}/pixel/{i}/0/0/0")
            time.sleep(0.2)

        return images

    # ======================================================
    # Génération image minimum
    # ======================================================

    def get_clean_image(self,images = None, save_dir = None, save_name= None, nb_image_used = 8):

        if images is None:
            images = self.get_multi_lighting_img(nb_img=nb_image_used)

        if len(images) == 0:
            raise ValueError("Aucune image")

        result = images[0].copy()

        for img in images[1:]:
            result = np.minimum(result, img)

        if save_dir != None:
            if save_name == None:
                self.save_image(img = result, save_dir=save_dir,)
            else:
                self.save_image(img = result, save_dir=save_dir, save_name=save_name)

        return result

    # ======================================================
    # Recherche image la plus récente
    # ======================================================

    @staticmethod
    def get_latest_image(folder=CLEAN_DATASET_DIR):
        files = list(folder.glob("*.jpg"))
        if not files:
            raise FileNotFoundError(folder)

        latest = max(files, key=os.path.getmtime)
        return cv2.imread(str(latest))

    # ======================================================
    # Segmentation ExG
    # ======================================================
    def get_img_contour(self,img,
                        min_area_px=20,
                        max_area_px=200,
                        min_circularity=0.8,debug = False):

        b, g, r = cv2.split(img)
        exg = (
            2 * g.astype(np.int16)
            - r.astype(np.int16)
            - b.astype(np.int16))

        exg = cv2.normalize(exg,None,0,255,cv2.NORM_MINMAX)
        exg = exg.astype(np.uint8)

        _, mask = cv2.threshold(exg,140,255,cv2.THRESH_BINARY)


        kernel = np.ones((3, 3), np.uint8)
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

        # sauvegarde debug contour
        img_contours = cv2.drawContours(img, valid_contours, -1, (0,255,0), 2)


        contour_file = (SEG_DATASET_DIR /f"{datetime.now():%Y%m%d_%H%M%S}.png")
        cv2.imwrite(str(contour_file),img_contours)

        if debug == True:
            cv2.imshow("Image", img)
            cv2.imshow("ExG", exg)
            cv2.imshow("Mask", mask)

            img_contours = img.copy()
            cv2.drawContours(img_contours, contours, -1, (0,255,0), 2)
            cv2.imshow("Contours", img_contours)

            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return valid_contours

    # ======================================================
    # Détection lentille isolée
    # ======================================================
    #si la distance minimale d'isolation ne fonctionne pour aucune lentille
    #ajouter un cas ou l'on prend juste la plus éloignés
    def detect_isolated_duckweed(self,valid_contours = None,debug=False):
        """
        Retourne la première lentille isolée trouvée.
        """
        if valid_contours is None:
            img_contours = self.get_latest_image(SEG_DATASET_DIR)
            valid_contours = self.get_img_contour(img = img_contours,debug = debug)

        if valid_contours == []:
            print("No lenses detected")
            return None

        centers = []
        for cnt in valid_contours:

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
                
                if min_dist > dist:
                    min_dist = min
                    isolated_lens = cnt
                
        return isolated_lens

    # ======================================================
    # Conversion pixel -> repère plateau
    # ======================================================

    def get_coordinate_from_pixel(
            self,
            px_low,
            px_high,
            camera_z_low,
            camera_z_high):

        center = np.array((640, 480), dtype=float)

        mm_per_pixel = 35 / 600

        p1 = np.array(px_low, dtype=float)
        p2 = np.array(px_high, dtype=float)

        # moyenne des positions pour x/y
        p = (p1 + p2) / 2

        x = (p[0] - center[0]) * mm_per_pixel + self.offset_x
        y = (p[1] - center[1]) * mm_per_pixel + self.offset_y

        # déplacement entre les deux images
        disparity = np.linalg.norm(p2 - p1)

        # Calibration expérimentale
        # h = a * disparity + b
        a = -0.12      # exemple
        b = 18.5

        height = a * disparity + b

        return (
            round(x, 3),
            round(y, 3),
            round(height, 3),
        )


