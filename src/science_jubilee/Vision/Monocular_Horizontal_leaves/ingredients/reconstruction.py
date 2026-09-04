from sacred import Ingredient
import open3d as o3d
import numpy as np
from pathlib import Path
import cv2
import importlib


reconstruction = Ingredient("reconstruction")

@reconstruction.config
def config():
    enabled = False
    # Valeurs par défaut pour la décimation et l'alpha shape
    alpha = 0.005
    decimate_ratio = 0.5
    camera=None
    meshing = True


def run_create_point_cloud(rgb: np.ndarray, depth_mm: np.ndarray, camera):
    print("[3D] Génération du nuage de points en mémoire...")

    rgb = np.asarray(rgb)
    depth_mm = np.asarray(depth_mm, dtype=np.float32)

    if rgb.ndim == 2:
        rgb = cv2.cvtColor(rgb, cv2.COLOR_GRAY2RGB)
    elif rgb.shape[-1] == 4:
        rgb = rgb[..., :3]

    if rgb.shape[:2] != depth_mm.shape[:2]:
        rgb = cv2.resize(
            rgb, (depth_mm.shape[1], depth_mm.shape[0]), interpolation=cv2.INTER_LINEAR
        )

    h, w = depth_mm.shape[:2]

    # Utilisation directe des attributs K et dist de l'objet camera
    K = np.array(camera.K, dtype=np.float32)
    dist_np = np.array(camera.dist, dtype=np.float32)

    # Nettoyage des valeurs aberrantes
    depth_mm[np.isinf(depth_mm)] = 0.0
    depth_mm[np.isnan(depth_mm)] = 0.0
    depth_mm_flat = depth_mm.flatten()

    # 2. Création de la grille de pixels et correction de la distorsion
    u_grid, v_grid = np.meshgrid(np.arange(w), np.arange(h))
    points_2d = np.column_stack((u_grid.ravel(), v_grid.ravel())).astype(np.float32).reshape(-1, 1, 2)
    
    undistorted_pts = cv2.undistortPoints(points_2d, K, dist_np)
    x_norm = undistorted_pts[:, 0, 0].reshape(-1)
    y_norm = undistorted_pts[:, 0, 1].reshape(-1)

    # 3. Filtrage des pixels valides (profondeur > 0)
    valid = depth_mm_flat > 0
    valid_rgb = valid.reshape(-1)
    valid_mask = valid.reshape(h, w)
    z = depth_mm_flat[valid_rgb] / 1000.0  # Conversion mm -> mètres pour Open3D

    # Reprojection 3D
    x = x_norm[valid_rgb] * z
    y = y_norm[valid_rgb] * z
    
    
    y = -y
    z = -z
    xyz_map = np.full((h, w, 3), np.nan, dtype=np.float32)
    xyz_map[valid_mask] = np.column_stack((x, y, z))
    points = np.vstack((x, y, z)).T

    rgb_flat = rgb.reshape(-1, rgb.shape[-1])
    colors = rgb_flat[valid_rgb] / 255.0

    print(f"[3D] Nuage brut généré avec {len(points)} points.")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)

    # 4. Nettoyage du bruit (Statistical Outlier Removal)
    print("[3D] Filtrage statistique des valeurs aberrantes...")
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

    return pcd,xyz_map

def run_meshing(pcd, alpha=0.005, decimate_ratio=0.5):
    # Mesh creation from alpha shape method
    pcd_downsampled = pcd.voxel_down_sample(voxel_size=0.0005)
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd_downsampled, alpha)
    # Cleaning
    mesh.compute_vertex_normals()
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()
    print(f"Triangles generated : {len(mesh.triangles):,}".replace(",", " "))

    # Simple Quadratic decimation to prevent  heavy files
    if decimate_ratio < 1.0:
        target_faces = int(len(mesh.triangles) * decimate_ratio)
        print(
            f" Quadratic decimation, keeping only {target_faces:,} faces.".replace(
                ",", " "
            )
        )
        mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_faces)
        mesh.compute_vertex_normals()  # Recalcul des normales après la déformation
    return mesh

@reconstruction.capture
def run_reconstruction(
    image: np.ndarray, 
    depth_mm: np.ndarray, 
    camera,                
    alpha: float,
    decimate_ratio: float,
    output_dir: str, 
    image_name: str = "image.jpg",
    meshing: bool = True
):
    # Préparation des dossiers et chemins
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    stem = Path(image_name).stem
    
    image_file = output_path / f"{stem}_input.jpg"
    depth_file = output_path / f"{stem}_depth_mm.npy"
    pcd_file = output_path / f"{stem}_point_cloud.ply"
    mesh_file = output_path / f"{stem}_mesh.ply"

    # Sauvegarde des données brutes
    image_bgr = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)
    cv2.imwrite(str(image_file), image_bgr)
    np.save(depth_file, np.asarray(depth_mm))

    # 1. Pipeline Nuage de points (passage de l'objet camera)
    point_cloud, xyz_map = run_create_point_cloud(np.asarray(image), np.asarray(depth_mm), camera)
    o3d.io.write_point_cloud(str(pcd_file), point_cloud)
    print(f"[+] Nuage de points sauvegardé : {pcd_file}")
    mesh=None  # Initialisation de la variable mesh pour éviter les erreurs si meshing est False
    # 2. Pipeline Maillage
    if meshing:
        mesh = run_meshing(point_cloud, alpha=alpha, decimate_ratio=decimate_ratio)
        o3d.io.write_triangle_mesh(str(mesh_file), mesh)
        print(f"[+] Maillage sauvegardé : {mesh_file}")

    return {
        "xyz_map": xyz_map,
        "point_cloud": point_cloud,
        "mesh": mesh,
        "pcd_path": str(pcd_file),
        "mesh_path": str(mesh_file)
    }