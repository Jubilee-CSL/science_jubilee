from sacred import Ingredient

import cv2
import numpy as np


depth_scaling = Ingredient("depth_scaling")


@depth_scaling.capture
def run_scale_depth(
    image,
    depth_map,
    tray_mask,
    cube_mask,
    tray_z_mm,
    plant_height=None,
    scale_cube=None,
):
    """Scale monocular depth to millimetres using tray or cube references."""
    image = np.asarray(image)
    depth_map = np.asarray(depth_map, dtype=np.float32)
    tray_mask = np.asarray(tray_mask)
    cube_mask = np.asarray(cube_mask)

    if image.shape[:2] != depth_map.shape[:2]:
        raise ValueError("image and depth_map must have the same height and width")
    if tray_mask.shape != depth_map.shape or cube_mask.shape != depth_map.shape:
        raise ValueError("tray_mask and cube_mask must match depth_map shape")

    tray_depth = depth_map[(tray_mask > 0) & np.isfinite(depth_map)]
    if tray_depth.size == 0 or np.isclose(np.max(tray_depth), 0.0):
        print("[DEPTH] Warning: tray mask empty or tray depth maximum is zero")
        max_tray_depth = 1.0
    else:
        max_tray_depth = float(np.max(tray_depth))

    print(
        f"[DEPTH] Tray pixels: {tray_depth.size}, "
        f"min={np.min(tray_depth) if tray_depth.size else 0:.4f}, "
        f"max={max_tray_depth:.4f}"
    )

    depth_mm = depth_map * (tray_z_mm / max_tray_depth)
    if plant_height is not None:
        depth_min = float(np.nanmin(depth_map))
        depth_range = max_tray_depth - depth_min
        if np.isclose(depth_range, 0.0):
            raise ValueError("Cannot use plant_height: depth range is zero")
        depth_mm = (depth_map - depth_min) * plant_height / depth_range + (tray_z_mm - plant_height)

    cube_depth = np.array([], dtype=np.float32)
    if scale_cube is not None:
        cube_depth = depth_map[(cube_mask > 0) & np.isfinite(depth_map)]
        if cube_depth.size >= 4:
            q1, q3 = np.percentile(cube_depth, [25, 75])
            iqr = q3 - q1
            filtered = cube_depth[
                (cube_depth >= q1 - 1.5 * iqr)
                & (cube_depth <= q3 + 1.5 * iqr)
            ]
            if filtered.size:
                cube_depth = filtered
        if cube_depth.size == 0 or np.isclose(np.max(cube_depth), 0.0):
            print("[DEPTH] Warning: cube mask empty or cube depth maximum is zero")
        else:
            cube_min = float(np.min(cube_depth))
            depth_range = max_tray_depth - cube_min
            if np.isclose(depth_range, 0.0):
                raise ValueError("Cannot use scale_cube: tray/cube depth range is zero")
            depth_mm = (depth_map - cube_min) * scale_cube / depth_range + (tray_z_mm - scale_cube)
            print(
                f"[DEPTH] Cube pixels: {cube_depth.size}, "
                f"min={cube_min:.4f}, max={np.max(cube_depth):.4f}"
            )

    depth_mm = np.nan_to_num(depth_mm, nan=400.0, posinf=400.0, neginf=400.0)
    print(f"[DEPTH] Scaled range: min={np.min(depth_mm):.2f} mm, max={np.max(depth_mm):.2f} mm")

    depth_preview = cv2.normalize(depth_mm, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    return {
        "depth_mm": depth_mm,
        "tray_depth": tray_depth,
        "cube_depth": cube_depth,
        "tray_depth_min": float(np.min(tray_depth)) if tray_depth.size else None,
        "tray_depth_max": max_tray_depth,
        "cube_depth_min": float(np.min(cube_depth)) if cube_depth.size else None,
        "cube_depth_max": float(np.max(cube_depth)) if cube_depth.size else None,
        "depth_preview": cv2.applyColorMap(depth_preview, cv2.COLORMAP_TURBO),
    }
