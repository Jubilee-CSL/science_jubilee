from sacred import Ingredient

import numpy as np
import open3d as o3d
from plyfile import PlyData

meshing_ing = Ingredient("meshing")


@meshing_ing.config
def config():
    alpha = 0.0038
    decimate_ratio = 0.8


@meshing_ing.capture
def run_meshing(input_ply, output_obj, alpha, decimate_ratio):
    vertex_data = PlyData.read(str(input_ply)).elements[0].data
    points_cam = np.column_stack(
        [vertex_data["x"], vertex_data["y"], vertex_data["z"]]
    )
    points = np.column_stack([points_cam[:, 0], -points_cam[:, 2], points_cam[:, 1]])
    sh_c0 = 0.28209479177387814
    colors = np.column_stack(
        [
            np.clip(vertex_data["f_dc_0"] * sh_c0 + 0.5, 0, 1),
            np.clip(vertex_data["f_dc_1"] * sh_c0 + 0.5, 0, 1),
            np.clip(vertex_data["f_dc_2"] * sh_c0 + 0.5, 0, 1),
        ]
    )
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd, alpha)
    mesh.compute_vertex_normals()
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()
    if decimate_ratio < 1.0:
        mesh = mesh.simplify_quadric_decimation(
            target_number_of_triangles=int(len(mesh.triangles) * decimate_ratio)
        )
        mesh.compute_vertex_normals()
    o3d.io.write_triangle_mesh(str(output_obj), mesh)
    return True
