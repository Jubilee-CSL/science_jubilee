import argparse
import json
import os
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"  # Allows using Cuda (necessary)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from rembg import new_session, remove

except Exception:  # pragma: no cover - optional dependency
    remove = None
    new_session = None

from src.inference_marigold import infer_depth_and_normals


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


def segment_plant_mask(image: np.ndarray, use_ai: bool = True) -> np.ndarray:
    if use_ai and remove is not None and new_session is not None:
        try:
            session = new_session("isnet-general-use")
            pil_image = Image.fromarray(cv2.cvtColor(image))
            transparent = remove(
                pil_image,
                session=session,
                alpha_matting=True,
                alpha_matting_foreground_threshold=240,
                alpha_matting_background_threshold=10,
                alpha_matting_erode_size=10,
            )
            alpha = np.array(transparent.getchannel("A"))
            mask = (alpha > 0).astype(np.uint8) * 255
            kernel = np.ones((3, 3), np.uint8)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
            return mask
        except Exception as exc:  # model runtime may fail
            print(
                f"[!] AI segmentation failed ({exc}), falling back to a HSV-based mask"
            )

    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_green = np.array([35, 40, 40], dtype=np.uint8)
    upper_green = np.array([95, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_green, upper_green)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


# Added the segmentation of cube for trying to reference our real height from the hight predicted by marigold depths
def segment_cube_mask(image: np.ndarray):
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([100, 100, 50], dtype=np.uint8)
    upper_blue = np.array([140, 255, 255], dtype=np.uint8)
    mask = cv2.inRange(hsv, lower_blue, upper_blue)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    return mask


def segment_tray_mask(image: np.ndarray, margin_padding_px=20) -> np.ndarray:
    """
    Construction of the tray mask by searching for the ArUco codes on the corners (see printable aruco_reference.pdf )
    The sheet has to be placed on the center of the jubilee tray
    """
    # Configuration of aruco code detection using its corresponding dictionary name (in this cas we use the arUco code number 0 from DICT_4X4_50 )
    aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
    parameters = (
        cv2.aruco.DetectorParameters()
    )  # We dont need for custom parameters (real width, lenght, etc)
    detector = cv2.aruco.ArucoDetector(aruco_dict, parameters)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    corners, ids, rejected = detector.detectMarkers(gray)

    final_mask = np.zeros(image.shape[:2], dtype=np.uint8)

    if ids is None or len(corners) == 0:
        print("Any arUco code detected")
        return final_mask

    all_corners = np.vstack(corners).reshape(-1, 2)

    # Creation of the global tray mask by using the rectangle formed by the 4 arUco Codes
    rect = cv2.minAreaRect(all_corners)
    box = cv2.boxPoints(rect)
    box = np.int32(box)

    cv2.drawContours(final_mask, [box], 0, 255, thickness=cv2.FILLED)

    # Padding added to include the real AruCo codes padding from the printed sheet
    if margin_padding_px > 0:
        kernel = np.ones((margin_padding_px, margin_padding_px), np.uint8)
        final_mask = cv2.dilate(final_mask, kernel, iterations=1)

    return final_mask


def estimate_horizontal_targets(
    image_path: str,
    depth_path: str,
    normals_path: str,
    config: dict,
    use_ai: bool = True,
):
    image = cv2.imread(image_path)
    if image is None:
        raise FileNotFoundError(f"Unable to read input image: {image_path}")

    depth_map = np.load(depth_path).astype(np.float32)
    normals = np.load(normals_path).astype(np.float32)

    tray_mask = segment_tray_mask(image)
    plant_mask = segment_plant_mask(image, use_ai=use_ai)
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


def save_targets(
    output_dir: str,
    targets: list,
    image_path: str,
    tray_mask: np.ndarray,
    plant_mask: np.ndarray,
    depth_mm: np.ndarray,
):
    os.makedirs(output_dir, exist_ok=True)
    target_path = os.path.join(output_dir, "targets.json")
    with open(target_path, "w", encoding="utf-8") as handle:
        json.dump(targets, handle, indent=2)

    image = cv2.imread(image_path)
    if image is not None:
        overlay = image.copy()

        if tray_mask is not None and tray_mask.size > 0:
            tray_pixels = tray_mask > 0
            tray_color = np.array([255, 0, 0], dtype=np.uint8)
            overlay[tray_pixels] = np.clip(
                overlay[tray_pixels] * 0.7 + tray_color * 0.3, 0, 255
            ).astype(np.uint8)

        if plant_mask is not None and plant_mask.size > 0:
            plant_pixels = plant_mask > 0
            plant_color = np.array([0, 255, 0], dtype=np.uint8)
            overlay[plant_pixels] = np.clip(
                overlay[plant_pixels] * 0.7 + plant_color * 0.3, 0, 255
            ).astype(np.uint8)

        for target in targets:
            u, v = target["pixel"]
            cv2.circle(overlay, (int(u), int(v)), 8, (0, 0, 255), -1)
            cv2.putText(
                overlay,
                str(target["id"]),
                (int(u) + 8, int(v) - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 0, 255),
                1,
                cv2.LINE_AA,
            )

            xyz = target["xyz_mm"]
            label = f"x={xyz[0]:.1f} y={xyz[1]:.1f} z={xyz[2]:.1f}"
            cv2.putText(
                overlay,
                label,
                (int(u) + 8, int(v) + 12),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )

        cv2.imwrite(os.path.join(output_dir, "overlay_targets.png"), overlay)

    np.save(os.path.join(output_dir, "depth_mm.npy"), depth_mm)
    np.save(os.path.join(output_dir, "tray_mask.npy"), tray_mask)
    np.save(os.path.join(output_dir, "plant_mask.npy"), plant_mask)

    return target_path


def run_pipeline(
    image_path: str,
    output_dir: str,
    config_path: str = "config.yaml",
    use_ai: bool = True,
):
    config = {
        "camera": {},
        "physical": {},
    }
    if os.path.exists(config_path):
        import yaml

        with open(config_path, "r", encoding="utf-8") as handle:
            loaded = yaml.safe_load(handle) or {}
            config.update(loaded)

    depth_path, normals_path = infer_depth_and_normals(image_path, output_dir)
    targets, tray_mask, plant_mask, depth_mm = estimate_horizontal_targets(
        image_path, depth_path, normals_path, config, use_ai=use_ai
    )
    target_path = save_targets(
        output_dir, targets, image_path, tray_mask, plant_mask, depth_mm
    )

    print(f"[+] Found {len(targets)} horizontal leaf target(s)")
    for target in targets:
        print(
            f"    - id={target['id']} xyz={target['xyz_mm']} area_px={target['area_px']}"
        )
    print(f"[+] Target export saved to: {target_path}")
    return targets


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Estimate horizontal leaf surfaces and export camera-relative XYZ coordinates"
    )
    parser.add_argument("--image", required=True, help="Input image path")
    parser.add_argument("--output", default="output", help="Directory for outputs")
    parser.add_argument(
        "--config", default="config.yaml", help="Path to the YAML configuration file"
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable rembg-based plant segmentation and use HSV fallback",
    )
    args = parser.parse_args()

    run_pipeline(
        args.image, args.output, config_path=args.config, use_ai=not args.no_ai
    )
