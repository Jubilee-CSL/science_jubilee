import logging
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ==========================================================
# CONFIGURATION
# ==========================================================
REPO_ROOT = Path(__file__).resolve().parent.parent
RAW_DATASET_DIR = REPO_ROOT / "Raw_images"
SEG_DATASET_DIR = REPO_ROOT / "Filtered_images"

# Création du dossier s'il n'existe pas
SEG_DATASET_DIR.mkdir(parents=True, exist_ok=True)


# ======================================================
# Segmentation de la végétation (ExG)
# ======================================================
def get_img_contour(
    img, min_area_px=10, max_area_px=300, min_circularity=0.5, debug=False
):
    b, g, r = cv2.split(img)
    exg = 2 * g.astype(np.int16) - r.astype(np.int16) - b.astype(np.int16)
    exg = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    _, mask = cv2.threshold(exg, 170, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_contours = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_px or area > max_area_px:
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue

        circularity = 4 * np.pi * area / (perimeter**2)
        if circularity < min_circularity:
            continue

        valid_contours.append(cnt)

    return valid_contours


# ======================================================
# Détection de la lentille isolée
# ======================================================
def detect_isolated_duckweed(img, valid_contours=None, float_points=None, debug=False):
    if valid_contours is None:
        valid_contours = get_img_contour(img, debug=debug)

    if not valid_contours:
        logger.warning("Aucune lentille détectée.")
        return None

    float_center_2d = np.mean(float_points, axis=0)
    circumference = np.abs(float_points[0][0] - float_center_2d[0])

    centers = []
    for cnt in valid_contours:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            duck = np.array([cx, cy])
            dist = np.sqrt(np.sum((duck - float_center_2d) ** 2))
            if (dist) / circumference <= 0.8:
                centers.append((cx, cy))

    if not centers:
        return None
    if len(centers) == 1:
        return centers[0]

    # Trouver la lentille la plus isolée (celle dont le voisin le plus proche est le plus éloigné)
    max_min_dist = -1
    isolated_lens = None

    for i, center in enumerate(centers):
        mini_dist = float("inf")
        for j, other in enumerate(centers):
            if i == j:
                continue
            dist = np.linalg.norm(np.array(center) - np.array(other))
            if dist < mini_dist:
                mini_dist = dist

        # On cherche le point dont la distance MINIMALE aux autres est la MAXIMALE
        if mini_dist > max_min_dist:
            max_min_dist = mini_dist
            isolated_lens = center

    return isolated_lens


# =======================================
# Détection du flotteur (Excess Blue)
# =======================================
def get_float_points(img, min_area_px=250, min_circularity=0.7) -> np.ndarray:
    b, g, r = cv2.split(img)
    # L'équation que vous utilisiez privilégie le bleu
    exb = 2 * b.astype(np.int16) - g.astype(np.int16) - r.astype(np.int16)
    exb = cv2.normalize(exb, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    _, mask = cv2.threshold(exb, 140, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid_contours = []

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_px:
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter > 0:
            circularity = 4 * np.pi * area / (perimeter**2)
            if circularity >= min_circularity:
                valid_contours.append(cnt)

    if not valid_contours:
        raise ValueError("Pas de flotteur détecté, changez les paramètres.")

    # On prend le plus gros contour valide s'il y en a plusieurs
    best_cnt = max(valid_contours, key=cv2.contourArea)
    (x, y), r_circle = cv2.minEnclosingCircle(best_cnt)

    image_points = np.array(
        [[x - r_circle, y], [x, y - r_circle], [x + r_circle, y], [x, y + r_circle]],
        dtype=np.float32,
    )

    return image_points


# =======================================
# Estimation de la profondeur PnP
# =======================================
def estimate_float_pose(camera, image_points, radius_mm):
    object_points = np.array(
        [[-radius_mm, 0, 0], [0, -radius_mm, 0], [radius_mm, 0, 0], [0, radius_mm, 0]],
        dtype=np.float32,
    )

    ok, rvecs, tvecs, errors = cv2.solvePnPGeneric(
        object_points, image_points, camera.K, camera.dist, flags=cv2.SOLVEPNP_IPPE
    )

    if not ok:
        raise RuntimeError("solvePnPGeneric a échoué.")

    best = None
    bestErr = np.inf

    for rvec, tvec, err in zip(rvecs, tvecs, errors):
        R, _ = cv2.Rodrigues(rvec)
        # On rejette les poses où le flotteur serait derrière la caméra
        if tvec[2][0] <= 0:
            continue
        if err < bestErr:
            bestErr = err
            best = (R, tvec.reshape(3))

    if best is None:
        raise RuntimeError("Aucune solution PnP valide vers l'avant (Z > 0).")

    return best[1]  # Retourne uniquement Tcf (le vecteur de translation)


# ======================================================
# Conversion pixel -> repère caméra (3D)
# ======================================================
def get_lens_position(camera, lens_pixel, water_level):
    u, v = lens_pixel
    z = float(water_level)

    dist_np = np.array(camera.dist, dtype=np.float32)
    point_2d = np.array([[[u, v]]], dtype=np.float32)

    undistorted_pt = cv2.undistortPoints(point_2d, camera.K, dist_np)

    x_norm = undistorted_pt[0, 0, 0]
    y_norm = undistorted_pt[0, 0, 1]

    x = x_norm * z
    y = y_norm * z

    return np.array([x, y, z], dtype=np.float32)


# ======================================================
# Pipeline Principale
# ======================================================
def main(img, camera, float_radius_mm=25.0):
    """
    Détecte le flotteur pour estimer la profondeur, identifie une lentille d'eau isolée,
    génère une image de contrôle avec surimpressions, et retourne les coordonnées 3D
    de la lentille et du flotteur.
    """
    output_img = img.copy()

    # 1. Traitement du flotteur
    try:
        float_img_points = get_float_points(img)

        # Affichage des 4 points extremums du flotteur (jaune)
        for pt in float_img_points:
            cv2.circle(output_img, (int(pt[0]), int(pt[1])), 4, (0, 255, 255), -1)

        # Estimation de la pose (tvec correspond au centre 3D du flotteur)
        tvec = estimate_float_pose(camera, float_img_points, float_radius_mm)
        float_center_3d = tvec # Tableau [X, Y, Z] en millimètres
        water_level = tvec[2] - 1.5 # Coordonnée Z correction car le flotteur est en dessous de la surface de l'eau
        
        # Calcul et affichage du centre 2D en pixels (bleu)
        float_center_2d = np.mean(float_img_points, axis=0).astype(int)
        cv2.circle(output_img, tuple(float_center_2d), 5, (255, 0, 0), -1)
        cv2.putText(
            output_img,
            f"Flotteur ({float_center_3d})",
            (float_center_2d[0] + 10, float_center_2d[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 0, 0),
            2,
        )

    except Exception as e:
        logger.error(f"Erreur flotteur : {e}")
        return None, None

    # 2. Traitement de la lentille d'eau
    duckweed_tracked = detect_isolated_duckweed(img=img, float_points=float_img_points)
    duckweed_3d = None

    if duckweed_tracked:
        # Calcul de la position 3D par rapport à la caméra
        duckweed_3d = get_lens_position(camera, duckweed_tracked, water_level)

        # Dessin de la lentille choisie (rouge)
        cv2.circle(output_img, duckweed_tracked, 5, (0, 0, 255), -1)
        cv2.putText(
            output_img,
            f"Cible({duckweed_3d})",
            (duckweed_tracked[0] + 10, duckweed_tracked[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            2,
        )
    else:
        logger.warning("Impossible de trouver une lentille isolée.")

    # 3. Superposition des informations de profondeur (Z)
    text = f"Profondeur Z estimee: {water_level:.1f} mm"
    cv2.putText(
        output_img, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2
    )

    # 4. Sauvegarde de l'image de contrôle (le filtre)
    filename = SEG_DATASET_DIR / "latest.png"
    cv2.imwrite(str(filename), output_img)
    logger.info(f"Image de controle sauvegardee sous : {filename}")

    # Renvoie les coordonnées 3D de la lentille ET du centre du flotteur
    return duckweed_3d, float_center_3d
