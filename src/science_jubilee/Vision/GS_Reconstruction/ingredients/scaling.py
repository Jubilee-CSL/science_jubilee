from sacred import Ingredient

import json
import numpy as np
from plyfile import PlyData, PlyElement
from scipy.spatial.transform import Rotation

scaling = Ingredient("scaling")


@scaling.config
def config():
    cameras_span = None


@scaling.capture
def run_scale_by_cameras(input_ply, output_ply, cameras_json_path, cameras_span):
    with open(cameras_json_path, "r", encoding="utf-8") as handle:
        cameras = json.load(handle)
    positions = np.asarray([camera["position"] for camera in cameras], dtype=float)
    image_positions = []
    for camera in cameras:
        name = camera["img_name"]
        image_positions.append(
            [
                float(name.split("x")[1].split("_")[0]),
                float(name.split("y")[1].split("_")[0]),
                float(name.split("z")[1].split("_")[0]),
            ]
        )
    image_positions = np.asarray(image_positions)
    spans = (
        np.ptp(image_positions, axis=0) * 1e-3
        if cameras_span is None
        else np.asarray(cameras_span, dtype=float)
    )
    scales = spans / np.ptp(positions, axis=0)
    plydata = PlyData.read(str(input_ply))
    vertex_data = plydata.elements[0].data.copy()
    points = np.column_stack([vertex_data[name] for name in ("x", "y", "z")])
    points = Rotation.from_euler("xyz", [3.2, 0.8, 0.0], degrees=True).apply(points)
    vertex_data["x"], vertex_data["y"], vertex_data["z"] = (points * scales).T
    for name in [
        prop.name for prop in plydata.elements[0].properties if prop.name.startswith("scale_")
    ]:
        vertex_data[name] += np.log(np.mean(scales))
    PlyData([PlyElement.describe(vertex_data, "vertex")], text=False).write(str(output_ply))
    return True
