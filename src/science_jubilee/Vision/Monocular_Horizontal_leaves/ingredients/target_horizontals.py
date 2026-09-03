from sacred import Ingredient

import cv2
import numpy as np
from sklearn.cluster import DBSCAN


target_horizontals = Ingredient("target_horizontals")


def _camera_xyz_map(depth_mm, camera):
    depth_mm = np.asarray(depth_mm, dtype=np.float32)
    height, width = depth_mm.shape[:2]
    u_grid, v_grid = np.meshgrid(np.arange(width), np.arange(height))
    pixels = np.column_stack((u_grid.ravel(), v_grid.ravel())).astype(np.float32)
    undistorted = cv2.undistortPoints(
        pixels.reshape(-1, 1, 2),
        np.asarray(camera.K, dtype=np.float32),
        np.asarray(camera.dist, dtype=np.float32),
    )
    x_norm = undistorted[:, 0, 0].reshape(height, width)
    y_norm = undistorted[:, 0, 1].reshape(height, width)
    z_m = depth_mm / 1000.0
    return np.dstack((x_norm * z_m, -y_norm * z_m, -z_m))


@target_horizontals.capture
def run_estimate_horizontal_targets(
    image,
    depth_mm,
    point_cloud,
    labels_img,
    plant_mask,
    normals,
    min_area_px,
    max_area_px,
    cluster_eps_mm,
    cluster_eps_normal,
    normal_threshold,
    camera,
):
    """Select one stable horizontal region for each pre-segmented leaf."""
    image = np.asarray(image)
    depth_mm = np.asarray(depth_mm, dtype=np.float32)
    labels_img = np.asarray(labels_img)
    plant_mask = np.asarray(plant_mask)
    normals = np.asarray(normals, dtype=np.float32)
    if labels_img.shape != depth_mm.shape or plant_mask.shape != depth_mm.shape:
        raise ValueError("labels_img, plant_mask and depth_mm must have the same shape")
    if normals.shape[:2] != depth_mm.shape:
        raise ValueError("normals and depth_mm must have the same height and width")
    if point_cloud is None:
        raise ValueError("point_cloud is required")

    xyz_map = _camera_xyz_map(depth_mm, camera)
    normal_z = normals[:, :, 2]
    horizontal_mask = np.abs(normal_z) > normal_threshold
    final_labels_img = np.zeros(labels_img.shape, dtype=np.int32)
    selected_masks = []
    normal_stds = []
    stats = []
    targets = []
    debug_overlay = image.copy()
    if debug_overlay.ndim == 2:
        debug_overlay = cv2.cvtColor(debug_overlay, cv2.COLOR_GRAY2BGR)

    for leaf_id in [label for label in np.unique(labels_img) if label > 0]:
        leaf_mask = (labels_img == leaf_id) & (plant_mask > 0)
        candidate_mask = leaf_mask & horizontal_mask & (depth_mm > 0)
        candidate_coords = np.column_stack(np.where(candidate_mask))
        candidate_xyz = xyz_map[candidate_mask]
        if len(candidate_xyz) < min_area_px:
            continue

        spatial_labels = DBSCAN(
            eps=cluster_eps_mm / 1000.0,
            min_samples=max(1, min_area_px // 4),
            n_jobs=1,
        ).fit_predict(candidate_xyz)
        candidates = []
        for spatial_id in np.unique(spatial_labels):
            if spatial_id == -1:
                continue
            spatial_indices = np.where(spatial_labels == spatial_id)[0]
            if len(spatial_indices) < min_area_px:
                continue
            normals_for_cluster = normal_z[
                candidate_coords[spatial_indices, 0],
                candidate_coords[spatial_indices, 1],
            ].reshape(-1, 1)
            normal_labels = DBSCAN(
                eps=cluster_eps_normal,
                min_samples=max(1, min_area_px // 8),
                n_jobs=1,
            ).fit_predict(normals_for_cluster)
            for normal_id in np.unique(normal_labels):
                if normal_id == -1:
                    continue
                selected = spatial_indices[normal_labels == normal_id]
                if min_area_px <= len(selected) <= max_area_px:
                    values = normal_z[
                        candidate_coords[selected, 0],
                        candidate_coords[selected, 1],
                    ]
                    candidates.append((float(np.std(values)), selected))

        if not candidates:
            continue
        selected_std, selected_indices = min(candidates, key=lambda item: item[0])
        selected_coords = candidate_coords[selected_indices]
        selected_mask = np.zeros(labels_img.shape, dtype=np.uint8)
        selected_mask[selected_coords[:, 0], selected_coords[:, 1]] = 255
        final_labels_img[selected_mask > 0] = len(targets) + 1
        selected_masks.append(selected_mask)
        normal_stds.append(selected_std)

        ys, xs = np.where(selected_mask > 0)
        left, top, width, height = cv2.boundingRect(
            np.column_stack((xs, ys)).astype(np.int32)
        )
        weights = np.abs(normal_z[ys, xs])
        center_x = float(np.average(xs, weights=weights))
        center_y = float(np.average(ys, weights=weights))
        u, v = int(round(center_x)), int(round(center_y))
        xyz = xyz_map[v, u] * 1000.0
        stats.append({
            "leaf_id": int(leaf_id),
            "area_px": int(len(selected_indices)),
            "normal_std": selected_std,
            "bbox": [left, top, width, height],
        })
        targets.append({
            "id": len(targets) + 1,
            "leaf_id": int(leaf_id),
            "pixel": [u, v],
            "area_px": int(len(selected_indices)),
            "bbox": [left, top, width, height],
            "normal_confidence": float(normal_z[v, u]),
            "normal_std": selected_std,
            "xyz_mm": [float(value) for value in xyz],
            "normal": [float(value) for value in normals[v, u]],
        })
        cv2.rectangle(debug_overlay, (left, top), (left + width, top + height), (0, 255, 0), 2)
        cv2.drawMarker(debug_overlay, (u, v), (0, 255, 0), cv2.MARKER_CROSS, 10, 2)

    return {
        "targets": targets,
        "labels_img": final_labels_img,
        "selected_masks": selected_masks,
        "normal_stds": normal_stds,
        "stats": stats,
        "overlay": debug_overlay,
        "point_cloud": point_cloud,
    }