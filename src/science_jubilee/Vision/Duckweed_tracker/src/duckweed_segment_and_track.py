import logging
import random
from pathlib import Path

import cv2
import numpy as np
import math
import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
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
# Segmentation de la végétation (ExG - Méthode Classique)
# ======================================================
def get_img_contour(
    img, min_area_px=10, max_area_px=500, min_circularity=0.5, debug=False
):
    b, g, r = cv2.split(img)
    exg = 2 * g.astype(np.int16) - r.astype(np.int16) - b.astype(np.int16)
    exg = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    _, mask = cv2.threshold(exg, 160, 255, cv2.THRESH_BINARY)
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
# Segmentation de la végétation (AI - Méthode Cellpose)
# ======================================================
def get_img_contour_cellpose(
    img, diameter=8, min_area_px=10, max_area_px=300, min_circularity=0.5
):
    try:
        from cellpose import models
    except ImportError:
        logger.error("Erreur: Le module 'cellpose' n'est pas installé. Exécutez 'pip install cellpose'.")
        return []

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    model = models.CellposeModel(gpu=True, model_type='cyto2')
    masks, flows, styles = model.eval(img_rgb, diameter=diameter, channels=[2, 0])

    valid_contours = []
    num_cells = masks.max()
    for i in range(1, num_cells + 1):
        cell_mask = np.uint8(masks == i) * 255
        contours, _ = cv2.findContours(cell_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area_px or area > max_area_px:
                continue
            valid_contours.append(cnt)

    logger.info(f"Cellpose a detecté {len(valid_contours)} lentilles valides (sur {num_cells} candidates).")
    return valid_contours


# ======================================================
# Détection de la lentille isolée
# ======================================================
def detect_isolated_duckweed(img,marge=10, valid_contours=None, float_points=None, debug=False):
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
                (_, _), radius = cv2.minEnclosingCircle(cnt)
                centers.append(((cx, cy), float(radius)))

    if not centers:
        return None
    if len(centers) == 1:
        return centers[0][0]

    max_min_gap = -float("inf")
    isolated_lens = None

    for i, (center, radius) in enumerate(centers):
        min_gap = float("inf")
        for j, (other, other_radius) in enumerate(centers):
            if i == j:
                continue
            dist = np.linalg.norm(np.array(center) - np.array(other))
            gap = dist - radius - other_radius
            if gap < min_gap:
                min_gap = gap

        if min_gap > max_min_gap:
            max_min_gap = min_gap
            isolated_lens = center

    if max_min_gap < marge:
        if debug:
            logger.debug(
                f"Aucune lentille suffisamment isolée trouvée: meilleur écart {max_min_gap:.1f} < marge {marge}"
            )
        return None

    return isolated_lens


# =======================================
# Détection du flotteur (Excess Blue)
# =======================================
def get_float_points(img, min_area_px=250, min_circularity=0.7) -> np.ndarray:
    b, g, r = cv2.split(img)
    exb = 2 * b.astype(np.int16) - g.astype(np.int16) - r.astype(np.int16)
    exb = cv2.normalize(exb, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    _, mask = cv2.threshold(exb, 150, 255, cv2.THRESH_BINARY)
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
        if tvec[2][0] <= 0:
            continue
        if err < bestErr:
            bestErr = err
            best = (R, tvec.reshape(3))

    if best is None:
        raise RuntimeError("Aucune solution PnP valide vers l'avant (Z > 0).")

    return best[1]


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
# Fonctions de Trajectoire (RRT / Tracking)
# ======================================================
def check_collision(obstacle_mask, pt1, pt2):
    """
    Vérifie les collisions pour une machine se déplaçant en 'L' :
    D'abord sur l'axe X (jusqu'à x2), puis sur l'axe Y (jusqu'à y2).
    """
    x1, y1 = pt1
    x2, y2 = pt2
    
    # 1. Déplacement en X : On fixe Y = y1, on avance X de x1 vers x2
    x_min, x_max = min(x1, x2), max(x1, x2)
    # L'indexation numpy est [y, x]. On check tous les X entre x_min et x_max inclus
    if np.any(obstacle_mask[y1, x_min:x_max+1] > 0):
        return True
        
    # 2. Déplacement en Y : On fixe X = x2 (car on vient d'y arriver), on avance Y de y1 vers y2
    y_min, y_max = min(y1, y2), max(y1, y2)
    if np.any(obstacle_mask[y_min:y_max+1, x2] > 0):
        return True
        
    return False

def get_insertion_point(obstacle_mask, duckweed_goal, marge=30):
    """
    Cherche le point d'insertion le plus vaste sur toute l'image, 
    en considérant la lentille cible (et sa marge) comme un obstacle temporaire.
    """
    mask_for_insertion = obstacle_mask.copy()
    
    # 2. On ajoute la lentille cible avec sa marge de sécurité comme obstacle (en blanc)
    # marge est en pixels
    center = (int(duckweed_goal[0]), int(duckweed_goal[1]))
    radius = int(marge)
    cv2.circle(mask_for_insertion, center, radius, 255, -1)
    
    # 3. On cherche la zone libre (noir) la plus éloignée de tout obstacle
    free_space = cv2.bitwise_not(mask_for_insertion)
    dist_transform = cv2.distanceTransform(free_space, cv2.DIST_L2, 5)
    
    # max_loc renvoie les coordonnées (X, Y) du pixel ayant la plus grande distance
    _, _, _, max_loc = cv2.minMaxLoc(dist_transform)
    
    return max_loc

def rrt_path_planning(start_2d, goal_2d, obstacle_mask, marge, roi_mask, step_size=20, max_iter=3000):
    kernel_size = int(2 * marge + 1)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        # On dilate les obstacles (le blanc bave sur le noir)
    obstacle_mask = cv2.dilate(obstacle_mask, kernel) # on ajoute un bord de 2mm à tout les duckweed pour pas qu'elles soient aspirées par l'effet capillaire
    h, w = obstacle_mask.shape
    nodes = [{'pos': start_2d, 'parent': -1}]
    
    for _ in range(max_iter):
        if random.random() < 0.1:
            sample = goal_2d
        else:
            while True:
                rx = random.randint(0, w - 1)
                ry = random.randint(0, h - 1)
                if roi_mask[ry, rx] > 0:
                    sample = (rx, ry)
                    break
            
        nearest_idx = 0
        min_dist = float('inf')
        for i, n in enumerate(nodes):
            dist = np.hypot(n['pos'][0] - sample[0], n['pos'][1] - sample[1])
            if dist < min_dist:
                min_dist = dist
                nearest_idx = i
                
        nearest_node = nodes[nearest_idx]
        
        theta = math.atan2(sample[1] - nearest_node['pos'][1], sample[0] - nearest_node['pos'][0])
        new_x = int(nearest_node['pos'][0] + step_size * math.cos(theta))
        new_y = int(nearest_node['pos'][1] + step_size * math.sin(theta))
        
        new_x = max(0, min(w - 1, new_x))
        new_y = max(0, min(h - 1, new_y))
        new_pos = (new_x, new_y)
        
        if not check_collision(obstacle_mask, nearest_node['pos'], new_pos):
            nodes.append({'pos': new_pos, 'parent': nearest_idx})
            
            # Pour la validation finale du goal, on vérifie bien que c'est atteignable
            if np.hypot(new_pos[0] - goal_2d[0], new_pos[1] - goal_2d[1]) <= step_size:
                if not check_collision(obstacle_mask, new_pos, goal_2d):
                    nodes.append({'pos': goal_2d, 'parent': len(nodes) - 1})
                    
                    path = []
                    curr = len(nodes) - 1
                    while curr != -1:
                        path.append(nodes[curr]['pos'])
                        curr = nodes[curr]['parent']
                    return path[::-1]
                    
    logger.warning("RRT n'a pas trouvé de chemin dans la limite d'itérations.")
    return None

def smooth_path(path_2d, obstacle_mask):
    if not path_2d or len(path_2d) <= 2:
        return path_2d
        
    smoothed_path = [path_2d[0]]
    curr_idx = 0
    
    while curr_idx < len(path_2d) - 1:
        furthest_valid_idx = curr_idx + 1
        for i in range(len(path_2d) - 1, curr_idx, -1):
            # Le check_collision va valider si on peut relier 2 checkpoints éloignés 
            # avec la cinématique X puis Y
            if not check_collision(obstacle_mask, path_2d[curr_idx], path_2d[i]):
                furthest_valid_idx = i
                break
        smoothed_path.append(path_2d[furthest_valid_idx])
        curr_idx = furthest_valid_idx
        
    return smoothed_path


# ======================================================
# Pipeline Principale
# ======================================================
def main(img, camera, float_radius_mm=25.0, tool_radius_px=15, use_AI=False, cellpose_diameter=80):
    output_img = img.copy()
    checkpoints_3d = np.empty((0, 3), dtype=np.float32)

    # 1. Traitement du flotteur
    try:
        float_img_points = get_float_points(img)
        for pt in float_img_points:
            cv2.circle(output_img, (int(pt[0]), int(pt[1])), 4, (0, 255, 255), -1)

        tvec = estimate_float_pose(camera, float_img_points, float_radius_mm)
        float_center_3d = tvec
        water_level = tvec[2] - 1.5 
        
        float_center_2d = np.mean(float_img_points, axis=0).astype(int)
        cv2.circle(output_img, tuple(float_center_2d), 5, (255, 0, 0), -1)
        
        float_radius_px = int(np.linalg.norm(float_img_points[0] - float_center_2d))
        cv2.putText(
            output_img,
            f"Flotteur",
            (float_center_2d[0] + 10, float_center_2d[1]),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2,
        )

        conversion_factor = float_radius_mm / float_radius_px
        marge_insertion= 10 / conversion_factor  # marge de sécurité de 10mm convertie en pixels
        marge_prise=3 / conversion_factor  # marge de sécurité de 3mm convertie en pixels
        tool_radius_px = int(1.27 / conversion_factor)  # rayon de l'outil converti en pixels
    except Exception as e:
        logger.error(f"Erreur flotteur : {e}")
        return None, None, checkpoints_3d

    # 2. Récupération globale des contours
    if use_AI:
        logger.info("Détection des lentilles via Cellpose (IA)...")
        valid_contours = get_img_contour_cellpose(img, diameter=cellpose_diameter)
    else:
        logger.info("Détection des lentilles via Excess Green (Classique)...")
        valid_contours = get_img_contour(img)
    
    cv2.drawContours(output_img, valid_contours, -1, (0, 255, 0), 2)

    duckweed_tracked = detect_isolated_duckweed(img=img,marge=marge_prise, valid_contours=valid_contours, float_points=float_img_points)
    duckweed_3d = None

    if duckweed_tracked:
        duckweed_3d = get_lens_position(camera, duckweed_tracked, water_level)
        cv2.circle(output_img, duckweed_tracked, 5, (0, 0, 255), -1)
        cv2.putText(
            output_img,
            f"Cible",
            (duckweed_tracked[0] + 10, duckweed_tracked[1]),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2,
        )

        # 3. Path Planning Confiné
        roi_mask = np.zeros(img.shape[:2], dtype=np.uint8)
        cv2.circle(roi_mask, tuple(float_center_2d), float_radius_px, 255, -1)
        cv2.circle(output_img, tuple(float_center_2d), float_radius_px, (0, 255, 255), 2)

        target_cnt = None
        for cnt in valid_contours:
            if cv2.pointPolygonTest(cnt, duckweed_tracked, False) >= 0:
                target_cnt = cnt
                break

        obstacle_mask = np.zeros(img.shape[:2], dtype=np.uint8)
        for cnt in valid_contours:
            if cnt is not target_cnt: 
                cv2.drawContours(obstacle_mask, [cnt], -1, 255, thickness=cv2.FILLED)
                
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (tool_radius_px * 2, tool_radius_px * 2))
        obstacle_mask = cv2.dilate(obstacle_mask, kernel)

        outside_roi = cv2.bitwise_not(roi_mask)
        obstacle_mask = cv2.bitwise_or(obstacle_mask, outside_roi)

        insertion_2d = get_insertion_point(obstacle_mask,duckweed_tracked,marge=marge_insertion)
        cv2.circle(output_img, insertion_2d, 6, (255, 255, 0), -1) 
        cv2.putText(output_img, "Insertion", (insertion_2d[0]-30, insertion_2d[1]-10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 0), 2)

        path_2d = rrt_path_planning(insertion_2d, duckweed_tracked, obstacle_mask,marge=marge_prise, roi_mask=roi_mask)

        if path_2d:
            smoothed_path_2d = smooth_path(path_2d, obstacle_mask)
            
            pts_3d_list = []
            for i, pt in enumerate(smoothed_path_2d):
                if i < len(smoothed_path_2d) - 1:
                    next_pt = smoothed_path_2d[i+1]
                    
                    # Point d'angle (X d'abord, Y ensuite)
                    corner_pt = (next_pt[0], pt[1])
                    
                    # Dessiner le chemin en 'L' pour correspondre à la machine
                    # 1. Axe X
                    cv2.line(output_img, pt, corner_pt, (0, 165, 255), 2)
                    # 2. Axe Y
                    cv2.line(output_img, corner_pt, next_pt, (0, 165, 255), 2)
                    
                cv2.circle(output_img, pt, 3, (255, 0, 255), -1)
                
                # Conversion 3D
                pt_3d = get_lens_position(camera, pt, water_level)
                pts_3d_list.append(pt_3d)
                
            checkpoints_3d = np.array(pts_3d_list, dtype=np.float32)
            logger.info(f"Chemin planifie avec {len(checkpoints_3d)} checkpoints.")
        else:
            logger.warning("Aucun chemin viable trouve pour atteindre la lentille.")

    else:
        logger.warning("Impossible de trouver une lentille isolée.")

    text = f"Profondeur Z estimee: {water_level:.1f} mm"
    cv2.putText(
        output_img, text, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2
    )

    filename = SEG_DATASET_DIR / "latest.png"
    cv2.imwrite(str(filename), output_img)
    logger.info(f"Image de controle sauvegardee sous : {filename}")

    return duckweed_3d, float_center_3d, checkpoints_3d