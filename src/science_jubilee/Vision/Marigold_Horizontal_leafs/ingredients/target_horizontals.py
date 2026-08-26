from sacred import Ingredient

import cv2
import numpy as np
from pathlib import Path

from .filter_scene import segment_plant_mask, segment_tray_mask


target_horizontals = Ingredient("target_horizontals")


@target_horizontals.config
def config():
    pass

@target_horizontals.capture
def depth_to_camera_xyz(
    depth_map: np.ndarray, u: float, v: float, intrinsics: dict
) -> np.ndarray:
    # Thanks to the depth estimated by marigold we can compute the real world cordinates using camera pinhole model with iis calibrated camera parameters
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
    config: dict,
):
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Unable to read input image: {image_path}")

    depth_map = np.load(depth_path).astype(np.float32)
    normals = np.load(normals_path).astype(np.float32)

    tray_mask = segment_tray_mask(image)
    plant_mask = segment_plant_mask(image)
    tray_mask = tray_mask - plant_mask  ##Add cube mask

    tray_depth_values = depth_map[tray_mask > 0]
    print(
        f"[+] Tray depth values: {tray_depth_values.size} pixels, min={np.min(tray_depth_values):.2f}, max={np.max(tray_depth_values):.2f}"
    )

    """
    #Methode en scaling grace à un cube de référence
    cube_mask= segment_cube_mask(image)
    tray_mask= tray_mask- plant_mask-cube_mask
    tray_depth_values = depth_map[tray_mask > 0]
    print(f"[+] Tray depth values: {tray_depth_values.size} pixels, min={np.min(tray_depth_values):.2f}, max={np.max(tray_depth_values):.2f}")

    cube_depth_values= depth_map[cube_mask>0]
    print(f"Cube depth values: {cube_depth_values.size} pixels, min={np.min(cube_depth_values):.2f}, max={np.max(cube_depth_values):.2f}")


    if tray_depth_values.size == 0 or np.isclose(np.max(tray_depth_values), 0.0):
        scale = 1.0
    else:
        scale = 25/(np.max(tray_depth_values)-np.min(cube_depth_values))


    depth_mm=config["physical"]["tray_z_mm"] - (np.max(tray_depth_values) - depth_map)*scale            ##Méthode cube de référence


    """
    depth_mm = (
        depth_map * config["physical"]["plant_height_mm"]
        + config["physical"]["tray_z_mm"]
        - config["physical"]["plant_height_mm"]
    )
    print(
        f"[+] Depth map scaled convert to mm (tray_z_mm={config['physical']['tray_z_mm']}), depth_max_mm={np.max(depth_mm):.2f}) and depth_min_mm={np.min(depth_mm):.2f}"
    )

    normal_z = normals[:, :, 2]
    normal_threshold = float(config.get("filtering", {}).get("min_normal_z", 0.85))
    candidate_mask = cv2.bitwise_and(
        plant_mask, (normal_z > normal_threshold).astype(np.uint8) * 255
    )
    candidate_mask = cv2.bitwise_and(
        candidate_mask, (depth_mm > 0).astype(np.uint8) * 255
    )

    # Remove tiny border artifacts by eroding away the mask border and keeping only robust interior blobs.
    kernel = np.ones((3, 3), np.uint8)
    candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_OPEN, kernel)
    candidate_mask = cv2.morphologyEx(candidate_mask, cv2.MORPH_CLOSE, kernel)

    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(
        candidate_mask, connectivity=8
    )
    intrinsics = {
        "fx": float(config["camera"]["fx"]),
        "fy": float(config["camera"]["fy"]),
        "cx": float(config["camera"]["cx"]),
        "cy": float(config["camera"]["cy"]),
        "dist": config["camera"]["dist"],
    }
    # importing configuration from config.yaml
    filtering_cfg = config.get("filtering", {})
    min_area_px = int(filtering_cfg.get("min_area_px", 150))
    max_extent_ratio = float(filtering_cfg.get("max_extent_ratio", 8.0))
    min_border_margin_px = int(filtering_cfg.get("min_border_margin_px", 8))
    min_normal_confidence = float(filtering_cfg.get("min_normal_confidence", 0.70))
    depth_consistency_max_std_mm = float(
        filtering_cfg.get("depth_consistency_max_std_mm", 20.0)
    )
    depth_consistency_radius_px = int(
        filtering_cfg.get("depth_consistency_radius_px", 3)
    )

    targets = []
    for label_idx in range(1, num_labels):
        area = int(stats[label_idx, cv2.CC_STAT_AREA])
        left = int(stats[label_idx, cv2.CC_STAT_LEFT])
        top = int(stats[label_idx, cv2.CC_STAT_TOP])
        width = int(stats[label_idx, cv2.CC_STAT_WIDTH])
        height = int(stats[label_idx, cv2.CC_STAT_HEIGHT])

        # Filter the areas by all criteria described in config.yaml
        if area < min_area_px:
            continue

        extent = max(width, height) / max(min(width, height), 1)
        if extent > max_extent_ratio:
            continue

        border_distance = min(
            left, top, image.shape[1] - (left + width), image.shape[0] - (top + height)
        )
        if border_distance < min_border_margin_px:
            continue

        cx, cy = centroids[label_idx]
        u = int(round(cx))
        v = int(round(cy))
        # Computing real coordinates from pixel 2D coordinates
        xyz = depth_to_camera_xyz(depth_mm, u, v, intrinsics)
        normal_vector = normals[v, u]
        normal_norm = np.linalg.norm(normal_vector)
        if normal_norm < 1e-8:
            continue
        normal_vector = normal_vector / normal_norm
        normal_confidence = float(normal_vector[2])
        if normal_confidence < min_normal_confidence:
            continue

        mask = labels == label_idx
        h, w = depth_mm.shape[:2]
        local_depths = []
        for y in range(
            max(0, v - depth_consistency_radius_px),
            min(h, v + depth_consistency_radius_px + 1),
        ):
            for x in range(
                max(0, u - depth_consistency_radius_px),
                min(w, u + depth_consistency_radius_px + 1),
            ):
                if mask[y, x]:
                    local_depths.append(
                        float(np.asarray(depth_mm[y, x]).reshape(-1)[0])
                    )
        if len(local_depths) > 1:
            depth_std = float(np.std(local_depths))
            if depth_std > depth_consistency_max_std_mm:
                continue

        targets.append(
            {
                "id": label_idx,
                "pixel": [int(u), int(v)],
                "area_px": area,
                "bbox": [left, top, width, height],
                "extent": float(extent),
                "normal_confidence": normal_confidence,
                "depth_std_mm": depth_std if len(local_depths) > 1 else 0.0,
                "xyz_mm": [float(xyz[0]), float(xyz[1]), float(xyz[2])],
                "normal": [
                    float(normal_vector[0]),
                    float(normal_vector[1]),
                    float(normal_vector[2]),
                ],
            }
        )

    return targets, tray_mask, plant_mask, depth_mm


@target_horizontals.capture
def run_estimate_horizontal_targets(
	image,
	depth_map,
	normals,
	config,
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
	cv2.imwrite(str(image_path), image_bgr)
	np.save(depth_path, np.asarray(depth_map))
	np.save(normals_path, np.asarray(normals))
	targets, tray_mask, plant_mask, depth_mm = (
		estimate_horizontal_targets(
			str(image_path),
			str(depth_path),
			str(normals_path),
			config,
		)
		)

	overlay = image_bgr.copy()
	for target in targets:
		u, v = target["pixel"]
		cv2.circle(overlay, (u, v), 8, (0, 0, 255), -1)
		cv2.putText(
			overlay,
			str(target["id"]),
			(u + 8, v - 8),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.5,
			(0, 0, 255),
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
