import argparse
import json

import numpy as np
import open3d as o3d
from plyfile import PlyData, PlyElement
from scipy.spatial.transform import Rotation

def find_scales_from_cameras(cameras_json_path,cameras_span):
    """
    This code, search for the extreme positions of the cameras in the json file and compute the scale factors for x, y, and z based on the known dimensions of the cameras amplitude, we can determine an scale
    """
    with open(cameras_json_path, 'r') as f:
            cameras = json.load(f)
    max_axes = {'x': -np.inf, 'y': -np.inf, 'z': -np.inf}
    min_axes = {'x': np.inf, 'y': np.inf, 'z': np.inf}
    true_max_axes = {'x': -np.inf, 'y': -np.inf, 'z': -np.inf}
    true_min_axes = {'x': np.inf, 'y': np.inf, 'z': np.inf}
    for cam in cameras:
        cam_position = cam['position']
        if cam_position[0] > max_axes['x']:
            max_axes['x'] = cam_position[0]
        if cam_position[0] < min_axes['x']:
            min_axes['x'] = cam_position[0]
        if cam_position[1] > max_axes['y']:
            max_axes['y'] = cam_position[1]
        if cam_position[1] < min_axes['y']:     
            min_axes['y'] = cam_position[1]
        if cam_position[2] > max_axes['z']:
            max_axes['z'] = cam_position[2]
        if cam_position[2] < min_axes['z']:
            min_axes['z'] = cam_position[2]
        cam_name= cam['img_name']
        true_position=[0,0,0]
        true_position[0]=int(cam_name.split("x")[1].split("_")[0])
        true_position[1]=int(cam_name.split("y")[1].split("_")[0])
        true_position[2]=int(cam_name.split("z")[1].split("_")[0])
        if true_position[0] > true_max_axes['x']:
            true_max_axes['x'] = true_position[0]
        if true_position[0] < true_min_axes['x']:
            true_min_axes['x'] = true_position[0]
        if true_position[1] > true_max_axes['y']:
            true_max_axes['y'] = true_position[1]
        if true_position[1] < true_min_axes['y']:
            true_min_axes['y'] = true_position[1]
        if true_position[2] > true_max_axes['z']:
            true_max_axes['z'] = true_position[2]
        if true_position[2] < true_min_axes['z']:
            true_min_axes['z'] = true_position[2]
    # If cameras_span is None, compute it from the true positions found in the file
    if cameras_span is None:
        cameras_span = [
           ( true_max_axes['x'] - true_min_axes['x'])*1e-3,
            (true_max_axes['y'] - true_min_axes['y'])*1e-3,
            (true_max_axes['z'] - true_min_axes['z'])*1e-3
        ]
        print(f"True Span found:{cameras_span}")
    # Calculate the scale factors for each axis
    scale_x = cameras_span[0] / np.abs(max_axes['x'] - min_axes['x'])
    scale_y = cameras_span[1] / np.abs(max_axes['y'] - min_axes['y'])
    scale_z = cameras_span[2] / np.abs(max_axes['z'] - min_axes['z'])


    return (scale_x, scale_y, scale_z)

def process_and_align(input_ply, output_ply, scales, rot_scale=np.array([+3.2, +0.8, 0.0])):
    print(f"Chargement des Gaussiennes depuis {input_ply}...")
    plydata = PlyData.read(input_ply)
    vertex_data = plydata.elements[0].data.copy()

    # 1. On récupère les points bruts
    raw_x = np.array(vertex_data["x"])
    raw_y = np.array(vertex_data["y"])
    raw_z = np.array(vertex_data["z"])
    points_world = np.vstack((raw_x, raw_y, raw_z)).T

    # ==========================================
    # ROTATION GLOBALE (Positions ET Quaternions)
    # ==========================================
    r_global = Rotation.from_euler("xyz", rot_scale, degrees=True)

    # A. Rotation des positions
    points_world_rotated = r_global.apply(points_world)

    x = points_world_rotated[:, 0]
    y = points_world_rotated[:, 1]
    z = points_world_rotated[:, 2]

    # B. Rotation des splats (Quaternions internes)
    w = np.array(vertex_data["rot_0"])
    qx = np.array(vertex_data["rot_1"])
    qy = np.array(vertex_data["rot_2"])
    qz = np.array(vertex_data["rot_3"])

    # format scipy
    quats_scipy = np.vstack((qx, qy, qz, w)).T
    r_splats = Rotation.from_quat(quats_scipy)

    # Application de la rotation globale aux splats
    r_new = r_global * r_splats
    new_quats = r_new.as_quat()  # Retour en (x, y, z, w)

    # On remet les valeurs à jour dans vertex_data (en format w, x, y, z)
    vertex_data["rot_0"] = new_quats[:, 3]  # w
    vertex_data["rot_1"] = new_quats[:, 0]  # x
    vertex_data["rot_2"] = new_quats[:, 1]  # y
    vertex_data["rot_3"] = new_quats[:, 2]  # z
    
    x_scaled = x * scales[0]
    y_scaled = y * scales[1]
    z_scaled = z * scales[2]

    avg_scale = sum(scales) / 3.0
    scale_names = [
        p.name for p in plydata.elements[0].properties if p.name.startswith("scale_")
    ]
    for name in scale_names:
        vertex_data[name] += np.log(avg_scale)

    x_final = x_scaled
    y_final = y_scaled
    z_final = z_scaled
    # ==========================================
    # 5. SAUVEGARDE
    # ==========================================
    vertex_data["x"] = x_final
    vertex_data["y"] = y_final
    vertex_data["z"] = z_final

    new_element = PlyElement.describe(vertex_data, "vertex")
    PlyData([new_element], text=False).write(output_ply)
    print(f"Fichier final sauvegardé : {output_ply}")
    return new_element

def main(input_ply,output_ply,cameras_json_path,cameras_span):
    scales= find_scales_from_cameras(cameras_json_path=cameras_json_path,cameras_span=cameras_span)
    return(process_and_align(input_ply=input_ply,output_ply=output_ply,scales=scales))
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="PLY original")
    parser.add_argument(
        "--output", type=str, required=True, help="PLY mis à l'échelle et déplacé"
    )
    parser.add_argument(
        "--cameras_json",
        type=str,
        required=True,
        help="Chemin pour le fichier json de la reconstruction 3D qui a les cameras",
    )
    parser.add_argument(
        "--cameras_span",
        nargs=3,
        type=float,
        default=None,
        help="Trois valeurs (x y z) donnant l'étendue réelle des caméras (optionnel)",
    )
    args = parser.parse_args()

    main(args.input, args.output, args.cameras_json, args.cameras_span)