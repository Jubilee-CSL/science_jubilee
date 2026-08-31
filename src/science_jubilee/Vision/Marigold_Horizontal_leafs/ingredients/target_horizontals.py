from sacred import Ingredient
import cv2
import numpy as np
from pathlib import Path
from sklearn.cluster import DBSCAN

# Assurez-vous que ces imports correspondent à l'emplacement de vos fonctions
from .filter_scene import segment_plant_mask, segment_tray_mask

target_horizontals = Ingredient("target_horizontals")

@target_horizontals.config
def config():
    tray_z_mm: float
    min_area_px:float
    max_area_px:float
    cluster_eps_mm: float
    cluster_eps_normal:float
    camera:dict
    plant_height=None

@target_horizontals.capture
def depth_to_camera_xyz(
    depth_map: np.ndarray, u: float, v: float, intrinsics: dict
) -> np.ndarray:
    # Compute the real world coordinates using camera pinhole model with calibrated camera parameters
    h, w = depth_map.shape[:2]
    u0 = int(np.clip(round(u), 0, w - 1))
    v0 = int(np.clip(round(v), 0, h - 1))
    z_value = np.asarray(depth_map[v0, u0]).reshape(-1)[0]
    z = float(z_value)

    K = np.array(
        [
            [intrinsics["fx"], 0, intrinsics["cx"]],
            [0, intrinsics["fy"], intrinsics["cy"]],
            [0, 0, 1],
        ],
        dtype=np.float32,
    )
    # Improvement of the model by including the distortion parameters given py the opencv calibration
    dist_np = np.array(intrinsics["dist"], dtype=np.float32)
    point_2d = np.array([[[u, v]]], dtype=np.float32)

    undistorted_pt = cv2.undistortPoints(point_2d, K, dist_np)
    x_norm = undistorted_pt[0, 0, 0]
    y_norm = undistorted_pt[0, 0, 1]

    x = x_norm * z
    y = y_norm * z
    return np.array([x, y, z], dtype=np.float32)


@target_horizontals.capture
def estimate_horizontal_targets(
    image_path: str,
    depth_path: str,
    normals_path: str,
    tray_z_mm: float,
    normal_threshold:float,
    min_area_px:float,
    max_area_px:float,
    cluster_eps_mm: float,
    cluster_eps_normal:float,
    camera,
    plant_height=None,
):
    print("\n" + "=" * 50)
    print("[DEBUG] START TARGET ESTIMATION PIPELINE")
    print("=" * 50)

    image = cv2.imread(image_path)
    image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    if image is None:
        raise FileNotFoundError(f"Unable to read input image: {image_path}")

    depth_map = np.load(depth_path).astype(np.float32)
    normals = np.load(normals_path).astype(np.float32)

    tray_mask_raw = segment_tray_mask(image)
    plant_mask = segment_plant_mask(image)
    tray_mask = tray_mask_raw - plant_mask

    # -------------------------------------------------------------
    # 1. Depth Map Scaling
    # -------------------------------------------------------------
    tray_depth_values = depth_map[tray_mask > 0]
    if tray_depth_values.size == 0 or np.isclose(np.max(tray_depth_values), 0.0):
        print("[!] Warning: Tray mask is empty or max depth is 0!")
        max_tray_depth = 1.0
    else:
        max_tray_depth = np.max(tray_depth_values)

    print(
        f"[+] Tray depth values: {tray_depth_values.size} pixels, "
        f"min={np.min(tray_depth_values) if tray_depth_values.size > 0 else 0:.2f}, "
        f"max={max_tray_depth:.2f}"
    )

    depth_mm = depth_map * (tray_z_mm / max_tray_depth)
    if plant_height != None:
        depth_mm= (depth_map - np.min(depth_map) )*plant_height/(max_tray_depth-np.min(depth_mm)) + (tray_z_mm-plant_height)

    depth_mm[np.isinf(depth_mm)] = 400.0
    depth_mm[np.isnan(depth_mm)] = 400.0

    print(f"[1. Depth Scaling] Min: {np.min(depth_mm):.2f} mm | Max: {np.max(depth_mm):.2f} mm")

    # -------------------------------------------------------------
    # 2. Mask Generation (Normals & Depth)
    # -------------------------------------------------------------
    normal_z = normals[:, :, 2]
    normal_mask = (np.abs(normal_z) > normal_threshold).astype(np.uint8) * 255
    depth_valid_mask = (depth_mm > 0).astype(np.uint8) * 255

    candidate_mask = cv2.bitwise_and(plant_mask, normal_mask)
    candidate_mask = cv2.bitwise_and(candidate_mask, depth_valid_mask)

    # -------------------------------------------------------------
    # 3. Morphology Cleaning
    # -------------------------------------------------------------
    kernel = np.ones((3, 3), np.uint8)
    opened = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, kernel)
    candidate_mask = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel)

    # -------------------------------------------------------------
    # 4. Double Clustering DBSCAN (Distance 3D puis Différence Normale Z)
    # -------------------------------------------------------------

    # --- Étape A : Vectorisation du calcul XYZ (Pin-hole model) ---
    h, w = depth_mm.shape
    u_grid, v_grid = np.meshgrid(np.arange(w), np.arange(h))
    
    points_2d = np.column_stack((u_grid.ravel(), v_grid.ravel())).astype(np.float32).reshape(-1, 1, 2)
    
    K = camera.K
    dist_np = camera.dist

    undistorted_pts = cv2.undistortPoints(points_2d, K, dist_np)
    x_norm = undistorted_pts[:, 0, 0].reshape(h, w)
    y_norm = undistorted_pts[:, 0, 1].reshape(h, w)

    X = x_norm * depth_mm
    Y = y_norm * depth_mm
    XYZ_map = np.dstack((X, Y, depth_mm))

    # --- Étape B : Extraction des points candidats ---
    valid_mask = candidate_mask > 0
    valid_XYZ = XYZ_map[valid_mask]
    valid_normals_z = normal_z[valid_mask].reshape(-1, 1) # Format 2D requis pour DBSCAN
    valid_coords = np.column_stack(np.where(valid_mask))  # Format (y, x)

    print(f"[4. Clustering] 1er DBSCAN (Spatial 3D) sur {len(valid_XYZ)} points (eps={cluster_eps_mm}mm)...")
    
    # --- Étape C : Premier DBSCAN (Distance spatiale 3D) ---
    dbscan_spatial = DBSCAN(eps=cluster_eps_mm, min_samples=min_area_px // 4, n_jobs=-1)
    labels_spatial = dbscan_spatial.fit_predict(valid_XYZ)

    # Variables pour stocker les clusters finaux isolés
    final_labels_img = np.zeros((h, w), dtype=np.int32)
    current_label_id = 1
    split_by_normal_count = 0

    unique_spatial_labels = np.unique(labels_spatial)

    # --- Étape D : Deuxième DBSCAN (Orientation normal_z) sur chaque sous-groupe ---
    for sp_lbl in unique_spatial_labels:
        if sp_lbl == -1: 
            continue # Ignorer le bruit
            
        # Index des points appartenant à ce cluster spatial
        idx_cluster = np.where(labels_spatial == sp_lbl)[0]
        
        # S'il y a très peu de points, inutile de relancer un DBSCAN
        if len(idx_cluster) < min_area_px:
            continue
            
        # Récupération des valeurs normal_z du cluster
        cluster_normals = valid_normals_z[idx_cluster]
        
        # Second DBSCAN basé uniquement sur la similarité de l'orientation (normal_z)
        dbscan_norm = DBSCAN(eps=cluster_eps_normal, min_samples=min_area_px // 8, n_jobs=-1)
        labels_norm = dbscan_norm.fit_predict(cluster_normals)
        
        unique_norm_labels = np.unique(labels_norm)
        if len(unique_norm_labels) > 2: # Plus d'un groupe valide détecté (hors bruit -1)
            split_by_normal_count += 1
            
        # --- Étape E : Filtrage final et assignation sur l'image 2D ---
        for n_lbl in unique_norm_labels:
            if n_lbl == -1:
                continue
                
            idx_sub_cluster = idx_cluster[labels_norm == n_lbl]
            area = len(idx_sub_cluster)
            
            if min_area_px <= area <= max_area_px:
                y_c = valid_coords[idx_sub_cluster, 0]
                x_c = valid_coords[idx_sub_cluster, 1]
                final_labels_img[y_c, x_c] = current_label_id
                current_label_id += 1

    # --- Étape F : Construction des stats OpenCV manuellement ---
    # Cette étape remplace cv2.connectedComponentsWithStats pour empêcher
    # la refusion de 2 feuilles qui se touchent en 2D mais ont été séparées par DBSCAN.
    num_labels = current_label_id
    labels = final_labels_img
    stats = np.zeros((num_labels, 5), dtype=np.int32)
    centroids = np.zeros((num_labels, 2), dtype=np.float64)

    for i in range(1, num_labels):
        y_idx, x_idx = np.where(labels == i)
        stats[i, cv2.CC_STAT_LEFT] = x_idx.min()
        stats[i, cv2.CC_STAT_TOP] = y_idx.min()
        stats[i, cv2.CC_STAT_WIDTH] = x_idx.max() - x_idx.min() + 1
        stats[i, cv2.CC_STAT_HEIGHT] = y_idx.max() - y_idx.min() + 1
        stats[i, cv2.CC_STAT_AREA] = len(x_idx)
        centroids[i, 0] = x_idx.mean()
        centroids[i, 1] = y_idx.mean()

    total_blobs = num_labels - 1
    
    print(f"    -> Blobs spatiaux initiaux  : {len(unique_spatial_labels) - 1}")
    print(f"    -> Blobs scindés par normal : {split_by_normal_count}")
    print(f"    -> Blobs cibles finaux      : {total_blobs}\n")

    # -------------------------------------------------------------
    # 5. Target Extraction
    # -------------------------------------------------------------
    # -------------------------------------------------------------
    # 5. Target Extraction
    # -------------------------------------------------------------
    # Extraction des focales et du centre optique depuis la matrice K (3x3)
    intrinsics = {
        "fx": float(camera.K[0, 0]),
        "fy": float(camera.K[1, 1]),
        "cx": float(camera.K[0, 2]),
        "cy": float(camera.K[1, 2]),
        "dist": camera.dist,
    }
    targets = []
    
    for label_idx in range(1, num_labels):
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        left = int(stats[label_idx, cv2.CC_STAT_LEFT])
        top = int(stats[label_idx, cv2.CC_STAT_TOP])
        width = int(stats[label_idx, cv2.CC_STAT_WIDTH])
        height = int(stats[label_idx, cv2.CC_STAT_HEIGHT])

        if area < min_area_px:
            print(f"[-] Blob ID {label_idx} with area {area} rejected (less than {min_area_px})")
            continue

        cx, cy = centroids[label_idx]
        u = int(round(cx))
        v = int(round(cy))
        
        # Computing real coordinates from pixel 2D coordinates
        xyz = depth_to_camera_xyz(depth_mm, u, v, intrinsics)
        normal_vector = normals[v, u]
        
        # Calculate correct depth_std for this specific finalized blob
        final_blob_mask = (labels == label_idx)
        final_depth_std = float(np.std(depth_mm[final_blob_mask]))

        targets.append(
            {
                "id": label_idx,
                "pixel": [int(u), int(v)],
                "area_px": area,
                "bbox": [left, top, width, height],
                "normal_confidence": float(normal_vector[2]),
                "depth_std_mm": final_depth_std,
                "xyz_mm": [float(xyz[0]), float(xyz[1]), float(xyz[2])],
                "normal": [
                    float(normal_vector[0]),
                    float(normal_vector[1]),
                    float(normal_vector[2]),
                ],
            }
        )

    print(f"[+] Final valid targets detected: {len(targets)}")
    print("=" * 50 + "\n")

    return targets, tray_mask_raw, plant_mask, depth_mm


@target_horizontals.capture
def run_estimate_horizontal_targets(
    image,
    depth_map,
    normals,
    tray_z_mm,
    normal_threshold,
    min_area_px,
    max_area_px,
    cluster_eps_mm,
    cluster_eps_normal,
    camera,
    plant_height,
    output_dir,
    image_name="image.jpg",
):
    image_bgr = np.asarray(image)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    stem = Path(image_name).stem
    image_path = output_path / f"{stem}_input.jpg"
    depth_path = output_path / f"{stem}_depth.npy"
    normals_path = output_path / f"{stem}_normals.npy"
    
    image_out = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    cv2.imwrite(str(image_path), image_out)
    np.save(depth_path, np.asarray(depth_map))
    np.save(normals_path, np.asarray(normals))
    
    targets, tray_mask, plant_mask, depth_mm = estimate_horizontal_targets(
        str(image_path),
        str(depth_path),
        str(normals_path),
        tray_z_mm,
        normal_threshold,
        min_area_px,
        max_area_px,
        cluster_eps_mm,
        cluster_eps_normal,
        camera,
        plant_height,
    )

    overlay = image_bgr.copy()
    for target in targets:
        u, v = target["pixel"]
        left, top, width, height = target["bbox"]
        
        # Draw bounding box and marker
        cv2.rectangle(overlay, (left, top), (left + width, top + height), (0, 255, 0), 2)
        cv2.circle(overlay, (u, v), 6, (0, 0, 255), -1)
        
        # Draw ID and Z info
        z_mm = target["xyz_mm"][2]
        cv2.putText(
            overlay,
            f"ID:{target['id']} Z:{z_mm:.0f}mm",
            (left, max(15, top - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )

    return {
        "targets": targets,
        "image": image_bgr,
        "overlay": overlay,
        "tray_mask": tray_mask,
        "plant_mask": plant_mask,
        "depth_mm": depth_mm,
    }