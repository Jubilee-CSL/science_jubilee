import argparse

import numpy as np
import open3d as o3d
from plyfile import PlyData


def create_mesh_with_alpha_shape(
    input_ply, output_obj, grid_resolution=0.002, alpha=0.005, decimate_ratio=1.0
):

    # ---------------------------------------------------------
    # ÉTAPE 1 : CHARGEMENT ET TRANSFORMATION DES GAUSSIENNES
    # ---------------------------------------------------------
    print(f" Chargement du nuage de points : {input_ply}")
    plydata = PlyData.read(input_ply)
    vertex_data = plydata.elements[0].data

    # 1. On récupère les points bruts
    raw_x = np.array(vertex_data["x"])
    raw_y = np.array(vertex_data["y"])
    raw_z = np.array(vertex_data["z"])

    points_cam = np.vstack((raw_x, raw_y, raw_z)).T

    print("Transformation dans l'espace de la caméra...")

    x = points_cam[:, 0]
    y = -points_cam[:, 2]
    z = points_cam[:, 1]

    coords = np.vstack((x, y, z)).T

    # Extraction des Couleurs
    SH_C0 = 0.28209479177387814
    r = np.clip(vertex_data["f_dc_0"] * SH_C0 + 0.5, 0, 1)
    g = np.clip(vertex_data["f_dc_1"] * SH_C0 + 0.5, 0, 1)
    b = np.clip(vertex_data["f_dc_2"] * SH_C0 + 0.5, 0, 1)
    colors = np.vstack((r, g, b)).T

    visible_coords = coords
    visible_colors = colors
    # ---------------------------------------------------------
    # ÉTAPE 2 : MAILLAGE PAR ALPHA SHAPE (Open3D)
    # ---------------------------------------------------------
    print(f"Génération du maillage Alpha Shape (alpha={alpha}m)...")

    # Création du nuage de points Open3D
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(visible_coords)
    pcd.colors = o3d.utility.Vector3dVector(visible_colors)

    # Algorithme natif Alpha Shape
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd, alpha)

    # Nettoyage de base
    mesh.compute_vertex_normals()
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()

    print(f"Triangles générés : {len(mesh.triangles):,}".replace(",", " "))

    # ---------------------------------------------------------
    # ÉTAPE 3 : RÉDUCTION DES POLYGONES (DÉCIMATION)
    # ---------------------------------------------------------
    if decimate_ratio < 1.0:
        target_faces = int(len(mesh.triangles) * decimate_ratio)
        print(
            f" Décimation Quadrique... Réduction à {target_faces:,} faces.".replace(
                ",", " "
            )
        )
        # Simplification intelligente qui préserve les couleurs et les arêtes vives
        mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_faces)
        mesh.compute_vertex_normals()  # Recalcul des normales après la déformation

    # Sauvegarde finale
    o3d.io.write_triangle_mesh(output_obj, mesh)
    print(f" Succès ! Maillage sauvegardé sous : {output_obj}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Mesh 2.5D avec Open3D Alpha Shape, Scale et Decimation"
    )

    parser.add_argument("--input", type=str, required=True, help="Nuage .ply d'entrée")
    parser.add_argument(
        "--output", type=str, required=True, help="Maillage .obj de sortie"
    )

    # Paramètres de géométrie
    parser.add_argument(
        "--alpha",
        type=float,
        default=0.005,
        help="Valeur Alpha (Distance max entre points). Ex: 0.005 pour 5mm",
    )

    # Paramètres de transformation
    parser.add_argument(
        "--decimate",
        type=float,
        default=1.0,
        help="Ratio de triangles à garder (ex: 0.2 = garde 20%)",
    )

    args = parser.parse_args()

    create_mesh_with_alpha_shape(
        input_ply=args.input,
        output_obj=args.output,
        alpha=args.alpha,
        # scale=[0.025/1.25172,0.025/0.875492,0.025/0.556774],  #valeurs mesurées à la main
        # scale=[0.025/1.5250,0.025/0.9778,0.025/0.7968],
        decimate_ratio=args.decimate,
    )
