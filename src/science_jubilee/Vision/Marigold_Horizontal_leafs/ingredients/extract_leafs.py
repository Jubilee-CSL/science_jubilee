from sacred import Ingredient

import numpy as np
import open3d as o3d
import cv2


extract_leafs = Ingredient("extract_leafs")


@extract_leafs.config
def config():
    distance_threshold = 0.0092
    min_points = 20
    size_threshold = 1e-5
    shape_threshold = 0.98
    height_ratio = 0.1


@extract_leafs.capture
def run_extract_leaf_clusters(
    pcd,
    distance_threshold,
    min_points,
    size_threshold,
    shape_threshold,
    height_ratio,
    voxel_size=0.0005,
):
    downsampled = pcd.voxel_down_sample(voxel_size=voxel_size)
    labels = np.asarray(
        downsampled.cluster_dbscan(
            eps=distance_threshold, min_points=min_points, print_progress=False
        )
    )
    if labels.size == 0:
        return []
    points = np.asarray(downsampled.points)
    z_min = points[:, 2].min()
    total_height = points[:, 2].max() - z_min
    clusters = []
    for label in range(labels.max() + 1):
        cluster_points = points[labels == label]
        if len(cluster_points) < 3:
            continue
        eigenvalues = np.linalg.eigvalsh(np.cov(cluster_points.T))
        eval_sum = eigenvalues.sum()
        centroid = cluster_points.mean(axis=0)
        if (
            eigenvalues[-1] > size_threshold
            and eval_sum > 0
            and eigenvalues[-1] / eval_sum < shape_threshold
            and centroid[2] - z_min > total_height * height_ratio
        ):
            cluster = o3d.geometry.PointCloud()
            cluster.points = o3d.utility.Vector3dVector(cluster_points)
            clusters.append(cluster)
    return clusters


@extract_leafs.capture
def run_leaf_clusters_to_opencv(
    leaf_clusters,
    xyz_map,
    image_shape,
):
    """Project each 3D leaf cluster into one OpenCV label and binary mask."""
    height, width = image_shape[:2]
    xyz_map = np.asarray(xyz_map)
    labels_img = np.zeros((height, width), dtype=np.int32)
    contours = []
    masks = []
    stats = []
    centroids = []

    for label_id, leaf_pcd in enumerate(leaf_clusters, start=1):
        leaf_points = np.asarray(leaf_pcd.points)
        if leaf_points.size == 0:
            continue
        min_bound = leaf_points.min(axis=0)
        max_bound = leaf_points.max(axis=0)
        projected = np.all(
            (xyz_map >= min_bound) & (xyz_map <= max_bound), axis=2
        )
        mask = (projected.astype(np.uint8) * 255)
        contour_list, _ = cv2.findContours(
            mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contour_list:
            continue
        contour = max(contour_list, key=cv2.contourArea)
        if cv2.contourArea(contour) <= 0:
            continue
        cv2.drawContours(mask, [contour], -1, 255, thickness=-1)
        labels_img[mask > 0] = label_id
        moments = cv2.moments(contour)
        centroid = (
            moments["m10"] / moments["m00"],
            moments["m01"] / moments["m00"],
        ) if moments["m00"] else (0.0, 0.0)
        contours.append(contour)
        masks.append(mask)
        stats.append(cv2.boundingRect(contour))
        centroids.append(centroid)

    return {
        "labels_img": labels_img,
        "contours": contours,
        "masks": masks,
        "stats": stats,
        "centroids": centroids,
    }


@extract_leafs.capture
def run_extract_normal_leafs(leaf_clusters, horizontal_threshold=0.8):
    normals = run_compute_leaf_normals(leaf_clusters=leaf_clusters)
    z_axis = np.array([0.0, 1.0, 0.0])
    return [
        leaf
        for leaf, normal in zip(leaf_clusters, normals)
        if not np.isscalar(normal)
        and not np.any(np.isnan(normal))
        and abs(np.dot(normal, z_axis)) >= horizontal_threshold
    ]


@extract_leafs.capture
def run_compute_leaf_normals(leaf_clusters):
    normals = []
    for leaf in leaf_clusters:
        points = np.asarray(leaf.points)
        if len(points) < 3:
            normals.append(np.nan)
            continue
        _, eigenvectors = np.linalg.eigh(np.cov(points.T))
        normal = eigenvectors[:, 0]
        normals.append(normal / np.linalg.norm(normal))
    return normals