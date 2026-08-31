from sacred import Ingredient
import open3d as o3d
import numpy as np
from pathlib import Path
import cv2
import importlib

# Assurez-vous que le chemin d'import correspond bien à votre architecture
reconstruction_src = importlib.import_module(
    "science_jubilee.Vision.Marigold_Horizontal_leafs.src.3d_reconstruction"
)

reconstruction = Ingredient("reconstruction")

@reconstruction.config
def config():
    enabled = False
    # Valeurs par défaut pour la décimation et l'alpha shape
    alpha = 0.005
    decimate_ratio = 0.5
    camera=None


def create_point_cloud_from_depth(rgb: np.ndarray, depth_mm: np.ndarray, config: dict, camera):
    print("[3D] Génération du nuage de points en mémoire...")

    if rgb.shape[:2] != depth.shape[:2]:
        depth = cv2.resize(
            depth, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST
        )

    h, w = depth.shape[:2]

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
    z = depth_mm_flat[valid] / 1000.0  # Conversion mm -> mètres pour Open3D

    # Reprojection 3D
    x = x_norm[valid] * z
    y = y_norm[valid] * z

    # Changement d'axe pour s'adapter au repère standard (Y vers le haut, Z vers l'avant)
    y = -y
    z = -z

    points = np.vstack((x, y, z)).T
    
    # Extraction et normalisation des couleurs (Open3D attend des valeurs entre 0 et 1)
    colors = rgb.reshape(-1, 3)[valid] / 255.0

    print(f"[3D] Nuage brut généré avec {len(points)} points.")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)

    # 4. Nettoyage du bruit (Statistical Outlier Removal)
    print("[3D] Filtrage statistique des valeurs aberrantes...")
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

    return pcd


@reconstruction.capture
def run_create_point_cloud(
    image: np.ndarray, 
    depth_map: np.ndarray, 
    camera,                
    alpha: float,
    decimate_ratio: float,
    output_dir: str, 
    image_name: str = "image.jpg"
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
    np.save(depth_file, np.asarray(depth_map))

    # 1. Pipeline Nuage de points (passage de l'objet camera)
    point_cloud = create_point_cloud_from_depth(np.asarray(image), np.asarray(depth_map), config, camera)
    o3d.io.write_point_cloud(str(pcd_file), point_cloud)
    print(f"[+] Nuage de points sauvegardé : {pcd_file}")

    # 2. Pipeline Maillage
    mesh = meshing(point_cloud, alpha=alpha, decimate_ratio=decimate_ratio)
    o3d.io.write_triangle_mesh(str(mesh_file), mesh)
    print(f"[+] Maillage sauvegardé : {mesh_file}")

    return {
        "point_cloud": point_cloud,
        "mesh": mesh,
        "pcd_path": str(pcd_file),
        "mesh_path": str(mesh_file)
    }