from sacred import Ingredient

from pathlib import Path
import numpy as np
import open3d as o3d
from plyfile import PlyData, PlyElement

post_process = Ingredient("post_process")


@post_process.config
def config():
    bbox_size = 10000
    bbox_center = [0.0, 2, 0.0]
    elongation_threshold = 7.0
    scale_threshold = 1
    std_ratio = 3
    opacity_threshold = 0.07
    nb_neighbors = 60
    white_sat_thresh = 0.55
    white_val_thresh = 0.2


@post_process.capture
def run_filter_plants(
    input_ply,
    output_ply,
    bbox_size,
    bbox_center,
    elongation_threshold,
    scale_threshold,
    std_ratio,
    opacity_threshold,
    nb_neighbors,
    white_sat_thresh,
    white_val_thresh,
):
    input_path = Path(input_ply)
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    plydata = PlyData.read(str(input_path))
    vertex_data = plydata.elements[0].data
    x, y, z = (np.asarray(vertex_data[name]) for name in ("x", "y", "z"))
    half_size = bbox_size / 2.0
    cx, cy, cz = bbox_center
    inside = (
        (abs(x - cx) < half_size)
        & (abs(y - cy) < half_size)
        & (abs(z - cz) < half_size)
    )
    sh_c0 = 0.28209479177387814
    colors = np.column_stack(
        [
            np.clip(vertex_data["f_dc_0"] * sh_c0 + 0.5, 0, 1),
            np.clip(vertex_data["f_dc_1"] * sh_c0 + 0.5, 0, 1),
            np.clip(vertex_data["f_dc_2"] * sh_c0 + 0.5, 0, 1),
        ]
    )
    value = colors.max(axis=1)
    saturation = np.divide(
        colors.max(axis=1) - colors.min(axis=1),
        value,
        out=np.zeros_like(value),
        where=value > 0,
    )
    opacity = 1 / (1 + np.exp(-np.asarray(vertex_data["opacity"])))
    scale_names = [
        prop.name for prop in plydata.elements[0].properties if prop.name.startswith("scale_")
    ]
    real_scales = np.exp(np.column_stack([vertex_data[name] for name in scale_names]))
    scale_min = real_scales.min(axis=1)
    scale_max = real_scales.max(axis=1)
    valid = (
        inside
        & (opacity > opacity_threshold)
        & (scale_max < scale_threshold)
        & (scale_max / (scale_min + 1e-8) > elongation_threshold)
        & (value >= 0.05)
        & ~((saturation < white_sat_thresh) & (value > white_val_thresh))
    )
    filtered_data = vertex_data[valid]
    if len(filtered_data) > 0:
        points = np.column_stack(
            [filtered_data[name] for name in ("x", "y", "z")]
        )
        pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(points))
        _, indices = pcd.remove_statistical_outlier(
            nb_neighbors=nb_neighbors, std_ratio=std_ratio
        )
        filtered_data = filtered_data[indices]
    output_path = Path(output_ply)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    PlyData([PlyElement.describe(filtered_data, "vertex")], text=False).write(
        str(output_path)
    )
    return True
