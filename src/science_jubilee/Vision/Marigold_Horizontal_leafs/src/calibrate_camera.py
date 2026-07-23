#Calibration code from OpenCV calibration tutorials adapted for our calibration checkboard

import cv2
import numpy as np
import glob
import yaml
import os

CHECKERBOARD = (6, 8) 
input_calibration = r"C:\Users\Justin\Desktop\Jubilee\science_jubilee\src\science_jubilee\Vision\Marigold_Horizontal_leafs\input\calibration"

def calibrate(images_folder):

    objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)
    
    objpoints = [] 
    imgpoints = [] 
    

    images = glob.glob(f"{images_folder}/*.jpg") + glob.glob(f"{images_folder}/*.png") + glob.glob(f"{images_folder}/*.jpeg")
    
    if not images:
        raise FileNotFoundError(f"Aucune image trouvée dans le dossier : {images_folder}")

    print(f"Recherche du damier dans {len(images)} images...")
    
    gray = None
    images_valides = 0

    for fname in images:
        img = cv2.imread(fname)
        if img is None:
            continue
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Searching for corners
        ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)
        
        if ret:
            objpoints.append(objp)
        
            corners2 = cv2.cornerSubPix(gray, corners, (11,11), (-1,-1), 
                                        (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
            imgpoints.append(corners2)
            images_valides += 1
            print(f"  [OK] Damier détecté : {os.path.basename(fname)}")
        else:
            print(f"  [ÉCHEC] Damier introuvable : {os.path.basename(fname)}")
            
    if not objpoints:
        raise ValueError("Le damier n'a été détecté sur aucune image. Vérifie la taille de CHECKERBOARD.")
        
    print(f"\nCalcul de la calibration avec {images_valides} images valides...")
    
    # Calibration
    ret, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(objpoints, imgpoints, gray.shape[::-1], None, None)
    mean_error = 0
    erreurs_par_image = []

    for i in range(len(objpoints)):
        # On reprojette les points 3D idéaux sur l'image 2D avec notre matrice calculée
        imgpoints2, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
        
        # On compare la différence entre les points trouvés par OpenCV et notre modèle
        # On s'assure que les deux tableaux ont exactement la même forme (N points, 2 coordonnées x/y)
        pts_detectes = imgpoints[i].reshape(-1, 2)
        pts_reprojetes = imgpoints2.reshape(-1, 2)

        # On calcule la distance (norme L2) entre les points avec NumPy
        error = np.linalg.norm(pts_detectes - pts_reprojetes) / len(pts_reprojetes)
        erreurs_par_image.append(error)
        print(f"Image {i} - Erreur : {error:.3f} pixels")
        
        mean_error += error

    print(f"\nErreur totale moyenne : {mean_error/len(objpoints):.3f} pixels")

    return mtx, dist, ret

if __name__ == "__main__":
    try:
        mtx, dist, rms = calibrate(input_calibration)
        
        # Extraction of parameters
        fx, fy = mtx[0, 0], mtx[1, 1]
        cx, cy = mtx[0, 2], mtx[1, 2]
        
        print(f"\n[+] Calibration terminée !")
        print(f"    Erreur RMS (précision) : {rms:.3f} pixels (idéalement < 1.0)")
        print(f"    fx: {fx:.2f}, fy: {fy:.2f}")
        print(f"    cx: {cx:.2f}, cy: {cy:.2f}")
        
        # Saving on a yaml file
        config = {
            'camera': {
                'fx': float(fx), 
                'fy': float(fy), 
                'cx': float(cx), 
                'cy': float(cy),
                'dist': dist.flatten().tolist() 
            }
        }
        
        output_file = 'camera_params.yaml'
        with open(output_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
            
        print(f"[+] Paramètres sauvegardés dans '{output_file}'")
        
    except Exception as e:
        print(f"[-] Erreur lors de la calibration : {e}")