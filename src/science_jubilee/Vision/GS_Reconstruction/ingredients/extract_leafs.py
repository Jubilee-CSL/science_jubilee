from sacred import Ingredient

import numpy as np
import open3d as o3d


extract_leafs = Ingredient("extract_leafs")


@extract_leafs.config
def config():
    distance_threshold = 0.01
    min_points = 50
    size_threshold = 0.005
    shape_threshold = 0.85
    height_ratio = 0.2


@extract_leafs.capture
def run_extract_leaf_clusters(
    pcd,
    distance_threshold,
    min_points,
    size_threshold,
    shape_threshold,
    height_ratio,
):
    downsampled = pcd.voxel_down_sample(voxel_size=0.005)
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