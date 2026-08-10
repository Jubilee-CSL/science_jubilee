from pathlib import Path

import numpy as np
import open3d as o3d
from plyfile import PlyData, PlyElement


def filter_gaussians(
    input_ply,
    output_ply,
    opacity_threshold=0.1,
    scale_threshold=0.03,
    white_sat_thresh=0.15,
    white_val_thresh=0.6,
    ban_hue_min=10,
    ban_hue_max=50,
    elongation_threshold=2.0,
    bbox_size=100,
    bbox_center=[0.0, 0.0, 0.0],
    nb_neighbors=30,
    std_ratio=1.0,
):

    print(f"Loading Gaussians from {input_ply}...")
    input_ply_path = Path(input_ply)
    if not input_ply_path.exists():
        raise FileNotFoundError(input_ply_path)
    with input_ply_path.open("rb") as f:
        header = f.read(4)
    if not header.lower().startswith(b"ply"):
        raise ValueError(
            f"Invalid PLY file header for {input_ply_path}. "
            f"Found: {header!r}. Re-run reconstruction or regenerate the point cloud."
        )
    plydata = PlyData.read(input_ply)
    vertex_data = plydata.elements[0].data

    initial_count = len(vertex_data)
    print(f"Original splats: {initial_count}")

    # ----------------------------------------------------
    # 1. FILTRE SPATIAL ABSOLU (La Boîte Englobante / Cube)
    # ----------------------------------------------------
    x = np.array(vertex_data["x"])
    y = np.array(vertex_data["y"])
    z = np.array(vertex_data["z"])

    half_size = bbox_size / 2.0
    cx, cy, cz = bbox_center

    mask_x = (x > (cx - half_size)) & (x < (cx + half_size))
    mask_y = (y > (cy - half_size)) & (y < (cy + half_size))
    mask_z = (z > (cz - half_size)) & (z < (cz + half_size))

    is_inside_bbox = mask_x & mask_y & mask_z

    # ----------------------------------------------------
    # 2. COULEURS (Teinte, Saturation, Valeur)
    # ----------------------------------------------------
    SH_C0 = 0.28209479177387814
    r = np.clip(vertex_data["f_dc_0"] * SH_C0 + 0.5, 0, 1)
    g = np.clip(vertex_data["f_dc_1"] * SH_C0 + 0.5, 0, 1)
    b = np.clip(vertex_data["f_dc_2"] * SH_C0 + 0.5, 0, 1)

    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    delta = max_c - min_c

    value = max_c
    saturation = np.zeros_like(max_c)
    mask_nonzero = max_c > 0
    saturation[mask_nonzero] = delta[mask_nonzero] / max_c[mask_nonzero]

    hue = np.zeros_like(max_c)
    mask_delta = delta > 0

    mask_r = mask_delta & (max_c == r)
    hue[mask_r] = (60 * ((g[mask_r] - b[mask_r]) / delta[mask_r]) + 360) % 360

    mask_g = mask_delta & (max_c == g)
    hue[mask_g] = 60 * ((b[mask_g] - r[mask_g]) / delta[mask_g]) + 120

    mask_b = mask_delta & (max_c == b)
    hue[mask_b] = 60 * ((r[mask_b] - g[mask_b]) / delta[mask_b]) + 240

    # ----------------------------------------------------
    # 3. OPACITÉ ET GÉOMÉTRIE (Échelles et Étirement)
    # ----------------------------------------------------
    raw_opacity = np.array(vertex_data["opacity"])
    true_opacity = 1 / (1 + np.exp(-raw_opacity))

    scale_names = [
        p.name for p in plydata.elements[0].properties if p.name.startswith("scale_")
    ]
    scales_log = np.vstack([vertex_data[name] for name in scale_names]).T
    real_scales = np.exp(scales_log)

    scales_sorted = np.sort(real_scales, axis=1)
    s_min = scales_sorted[:, 0]
    s_max = scales_sorted[:, 2]

    elongation_ratio = s_max / (s_min + 1e-8)

    # ----------------------------------------------------
    # 4. CRÉATION DES MASQUES DE FILTRAGE COMBINÉS
    # ----------------------------------------------------
    mask_opacity = true_opacity > opacity_threshold
    mask_scale = s_max < scale_threshold
    is_elongated = elongation_ratio > elongation_threshold
    is_white_cloud = (saturation < white_sat_thresh) & (value > white_val_thresh)
    is_orange_artifact = (hue > ban_hue_min) & (hue < ban_hue_max) & (saturation > 0.2)

    # Restriction de la boîte englobante (is_inside_bbox)
    valid_mask = (
        is_inside_bbox
        & mask_opacity
        & mask_scale
        & is_elongated
        & (~is_white_cloud)
        & (~is_orange_artifact)
    )
    filtered_data = vertex_data[valid_mask]

    print(f"Splats restants après Bounding Box et Propriétés : {len(filtered_data)}")

    # ----------------------------------------------------
    # 5. FILTRE SPATIAL OPEN3D (Nettoyage fin)
    # ----------------------------------------------------
    if len(filtered_data) > 0:
        print("Analyse spatiale en cours (SOR)...")
        xyz = np.vstack((filtered_data["x"], filtered_data["y"], filtered_data["z"])).T
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(xyz)

        cl, valid_indices = pcd.remove_statistical_outlier(
            nb_neighbors=nb_neighbors, std_ratio=std_ratio
        )
        filtered_data = filtered_data[valid_indices]

    final_count = len(filtered_data)
    print(f"Splats finaux conservés : {final_count}")
    print(f"--> Total supprimé : {initial_count - final_count} splats.")

    # ----------------------------------------------------
    # 6. SAUVEGARDE
    # ----------------------------------------------------
    output_ply_path = Path(output_ply)
    output_ply_path.parent.mkdir(parents=True, exist_ok=True)
    new_element = PlyElement.describe(filtered_data, "vertex")
    PlyData([new_element], text=False).write(str(output_ply_path))
    print(f"Saved filtered splats to {output_ply_path}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)

    # Boîte englobante
    parser.add_argument(
        "--bbox_size",
        type=float,
        default=0.5,
        help="Taille du cube en mètres (0.5 = 50cm)",
    )
    parser.add_argument("--bbox_x", type=float, default=0.0, help="Centre du cube (X)")
    parser.add_argument("--bbox_y", type=float, default=0.0, help="Centre du cube (Y)")
    parser.add_argument("--bbox_z", type=float, default=0.0, help="Centre du cube (Z)")

    # Autres paramètres
    parser.add_argument("--opacity_threshold", type=float, default=0.1)
    parser.add_argument("--scale_threshold", type=float, default=0.03)
    parser.add_argument("--white_sat_thresh", type=float, default=0.15)
    parser.add_argument("--white_val_thresh", type=float, default=0.6)
    parser.add_argument("--ban_hue_min", type=float, default=10)
    parser.add_argument("--ban_hue_max", type=float, default=50)
    parser.add_argument("--elongation_threshold", type=float, default=2.0)
    parser.add_argument("--nb_neighbors", type=int, default=30)
    parser.add_argument("--std_ratio", type=float, default=1.0)

    args = parser.parse_args()

    center = [args.bbox_x, args.bbox_y, args.bbox_z]

    filter_gaussians(
        args.input,
        args.output,
        args.opacity_threshold,
        args.scale_threshold,
        args.white_sat_thresh,
        args.white_val_thresh,
        args.ban_hue_min,
        args.ban_hue_max,
        args.elongation_threshold,
        args.bbox_size,
        center,
        args.nb_neighbors,
        args.std_ratio,
    )
