import logging
import os
import time

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.hal.tool_changer import ToolChanger


import cv2
import numpy as np
import requests

logger = logging.getLogger(__name__)


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
@dataclass
class Neopixel:
    url: str = "http://10.0.9.55:5001"

    def pixel_on(self, led_index, r, g, b):
        requests.get(f"{self.url}/pixel/{led_index}/{r}/{g}/{b}")

    def pixel_off(self, led_index):
        requests.get(f"{self.url}/pixel/{led_index}/0/0/0")

    def all_pixel_on(self, r, g, b):
        requests.get(f"{self.url}/led/{r}/{g}/{b}")

    def all_pixel_off(self):
        requests.get(f"{self.url}/off")


class Camera:
    
    def __init__(self, motion,tool_changer):
        self.driver : MotionDriver= motion
        self.tool_changer : ToolChanger = tool_changer
        #position du point du plateau normale a la caméra

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
        
        self.url = f"http://{OCTOPI_IP}/webcam/?action=snapshot"

        #self.offset = ( 0, -25,11)   ##offset utilisé par quentin
        self.offset =(10,-13,16)

        self.T_machine_camera = np.array([0,0,0], dtype=np.float64)
        
    # ======================================================
    # Capture image
    # ======================================================
    def move_to_get_image(self):

        
        active_tool = self.tool_changer.get_active_tool_index()

        if active_tool == -1:
           active_tool_offset = (0,0,0)

        active_tool_offset = self.tool_changer.get_tool_offset(active_tool)

        x = active_tool_offset[0] - self.offset[0]
        y = active_tool_offset[1] - self.offset[1]
        z = 40
        self.driver.move({"Z":float(z)})
        self.driver.move({"X":float(x),
                          "Y":float(y),})
        
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
            self.save_image(img=images[i], save_dir=temp_dir)

            requests.get(f"{LED_SERVER}/pixel/{i}/0/0/0")
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
                        min_area_px=10,
                        max_area_px=300,
                        min_circularity=0.5,debug = False):

        b, g, r = cv2.split(img)
        exg = 2 * g.astype(np.int16) - r.astype(np.int16) - b.astype(np.int16)

        exg = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX)
        exg = exg.astype(np.uint8)

        _, mask = cv2.threshold(exg,170,255,cv2.THRESH_BINARY)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        valid_contours = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area_px:
                continue

            if area > max_area_px:
                continue

            perimeter = cv2.arcLength(cnt, True)
            if perimeter == 0:
                continue

            circularity = 4 * np.pi * area / (perimeter**2)
            if circularity < min_circularity:
                continue

            valid_contours.append(cnt)

        # sauvegarde debug contour
        img_contours = cv2.drawContours(img, valid_contours, -1, (0, 255, 0), 2)

        mask_file = SEG_DATASET_DIR / f"{datetime.now():%Y%m%d_%H%M%S}.png"
        cv2.imwrite(str(mask_file), mask)

        if debug == True:
            cv2.imshow("Image", img)
            cv2.imshow("ExG", exg)
            cv2.imshow("Mask", mask)

            img_contours = img.copy()
            cv2.drawContours(img_contours, valid_contours, -1, (0, 255, 0), 2)
            cv2.imshow("Contours", img_contours)

            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return valid_contours

    # ======================================================
    # Détection lentille isolée
    # ======================================================
    def detect_isolated_duckweed(self, valid_contours=None, debug=False):
        """
        Retourne la première lentille isolée trouvée.
        """
        if valid_contours is None:
            img_contours = self.get_latest_image(CLEAN_DATASET_DIR)
            valid_contours = self.get_img_contour(img=img_contours, debug=debug)

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
            mini_dist = 90000000

            for j, other in enumerate(centers):
                if i == j:
                    continue

                dist = np.linalg.norm(np.array(center) - np.array(other))

                if mini_dist > float(dist):
                    mini_dist = dist
                    isolated_lens = center

        self.save_image()
        return isolated_lens

    # =======================================
    # Détection du flotteur dans le puit
    # =======================================
    
    def _estimate_float_pose(self,image_points,radius_mm):

        object_points = np.array([[-radius_mm,0,0],
                                  [0,-radius_mm,0],
                                  [radius_mm,0,0],
                                  [0,radius_mm,0]],dtype=np.float32)

        ok,rvecs,tvecs,errors = cv2.solvePnPGeneric(
            object_points,image_points,
            self.K,
            self.dist,
            flags=cv2.SOLVEPNP_IPPE
        )

        if not ok:
            raise RuntimeError("solvePnPGeneric failed")

        best=None
        bestErr=np.inf

        for rvec,tvec,err in zip(rvecs,tvecs,errors):
            R,_=cv2.Rodrigues(rvec)

            if tvec[2] <=0:
                continue

            if err<bestErr:
                bestErr=err
                best=(R,tvec.reshape(3))

        if best is None:
            raise RuntimeError("No valid PnP solution")

        Rcf,Tcf=best
        Rmf=self.R_machine_camera @ Rcf
        Tmf=self.R_machine_camera @ Tcf + self.T_machine_camera

        return Rmf,Tmf
    
    def _pixel_to_ray(self,pixel):

        pts=np.array(pixel,dtype=np.float32).reshape(1,1,2)
        pts=cv2.undistortPoints(pts,self.K,self.dist)

        ray=np.array([pts[0,0,0],pts[0,0,1],1])
        ray/=np.linalg.norm(ray)

        return self.R_machine_camera @ ray
        
    def get_float_points(self,img,min_area_px=250,min_circularity=0.7,debug=False) -> np.array:

        b, g, r = cv2.split(img)
        exg = (- g.astype(np.int16)- r.astype(np.int16) + 2 * b.astype(np.int16))

        exg = cv2.normalize(exg,None,0,255,cv2.NORM_MINMAX)
        exg = exg.astype(np.uint8)

        _, mask = cv2.threshold(exg,170,255,cv2.THRESH_BINARY)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask,cv2.MORPH_OPEN,kernel)
        mask = cv2.morphologyEx(mask,cv2.MORPH_CLOSE,kernel)

        contours, _ = cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        
        valid_contours = []

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area_px:
                continue

            perimeter = cv2.arcLength(cnt,True)
            if perimeter == 0:
                continue

            circularity = (4* np.pi* area/ (perimeter ** 2))
            if circularity < min_circularity:
                continue

            valid_contours.append(cnt)

        # sauvegarde debug contour
        
        if valid_contours is not None and len(valid_contours) == 1:
            (x, y), r = cv2.minEnclosingCircle(valid_contours[0])  
        else:
            raise ValueError("Pas de flotteur détecter, changer les paramètres")

        image_points = np.array([[x - r, y],
                                 [x, y - r],
                                 [x + r, y],
                                 [x, y + r]], dtype=np.float32)
    
        if debug == True:
            cv2.imshow("Image", img)
            cv2.imshow("ExG", exg)
            cv2.imshow("Mask", mask)

            img_contours = img.copy()
            cv2.drawContours(img_contours, valid_contours, -1, (0,255,0), 2)
            cv2.imshow("Contours", img_contours)

            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return image_points
     
    # ======================================================
    # Conversion pixel -> repère plateau
    # ======================================================    
    #fonction a placer dans une classe plus adapté
    def get_lens_position(self,lens_pixel,float_points,float_radius_mm):
        
        Rmf,Tmf = self._estimate_float_pose(float_points,float_radius_mm)
        ray=self._pixel_to_ray(lens_pixel)
        origin=self.T_machine_camera
  
        normal=Rmf[:,2]
        alpha=np.dot(normal,Tmf-origin)/np.dot(normal,ray)
        lens3D=origin+alpha*ray

        return lens3D

    def get_lens_coordinate(self, lens_pos_px, well,img) -> tuple:
        #matrice de transformation référentiel caméra / plateau 
        """
        X_cam = X_jubilee
        Y_cam = -Y_cam
        Pour les images opencv le 0 0 est en haut a gauche
        """

        taille_img = img.shape
        # l'objet well contient ses propriétés géométriques notamment le diamètre
        diameter = well.diameter
        # et la postion centrale du puit dans le réferentiel du plateau
        center_x = well.x
        center_y = well.y
        # on considère que le puit est centré sur l'image
        center_x_px = taille_img[1] / 2
        center_y_px = taille_img[0] / 2
        logger.info(taille_img)

        # On détecte l'équivalent en pixel avec du traitement d'image pour ce construire une échelle, 1 point du périmètre suffit
        diameter_px = taille_img[0]
        logger.info("diamètre = %f", diameter_px)

        scale = diameter / diameter_px
        logger.info("scale  = %f", scale)

        delta_x = (lens_pos_px[0] - center_x_px) * scale
        delta_y = -(lens_pos_px[1] - center_y_px) * scale

        logger.info("delta x  = %f", delta_x)
        logger.info("delta y  = %f", delta_y)

        lens_pos_x = center_x + delta_x
        lens_pos_y = center_y + delta_y

        return (lens_pos_x, lens_pos_y)
