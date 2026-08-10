import numpy as np
from plyfile import PlyData, PlyElement
import open3d as o3d
import argparse
from scipy.spatial.transform import Rotation
#import extract_scale_cube
def rgb_to_hsv(r, g, b):
    max_c = np.maximum(np.maximum(r, g), b)
    min_c = np.minimum(np.minimum(r, g), b)
    delta = max_c - min_c
    
    v = max_c
    s = np.zeros_like(max_c)
    s[max_c > 0] = delta[max_c > 0] / max_c[max_c > 0]
    
    h = np.zeros_like(max_c)
    mask = delta > 0
    
    idx = mask & (max_c == r)
    h[idx] = (60 * ((g[idx] - b[idx]) / delta[idx]) + 360) % 360
    
    idx = mask & (max_c == g)
    h[idx] = 60 * ((b[idx] - r[idx]) / delta[idx]) + 120
    
    idx = mask & (max_c == b)
    h[idx] = 60 * ((r[idx] - g[idx]) / delta[idx]) + 240
    
    return h, s, v

def process_and_align(input_ply, output_ply, rot_scale=np.array([+3.2, +0.8, 0.0])):
    print(f"Chargement des Gaussiennes depuis {input_ply}...")
    plydata = PlyData.read(input_ply)
    vertex_data = plydata.elements[0].data.copy()
    
    # 1. On récupère les points bruts
    raw_x = np.array(vertex_data['x'])
    raw_y = np.array(vertex_data['y'])
    raw_z = np.array(vertex_data['z'])
    points_world = np.vstack((raw_x, raw_y, raw_z)).T
    
    # ==========================================
    # ROTATION GLOBALE (Positions ET Quaternions)
    # ==========================================
    r_global = Rotation.from_euler('xyz', rot_scale, degrees=True)
    
    # A. Rotation des positions
    points_world_rotated = r_global.apply(points_world)
    
    x = points_world_rotated[:, 0]
    y = points_world_rotated[:, 1]
    z = points_world_rotated[:, 2]

    # B. Rotation des splats (Quaternions internes)
    w = np.array(vertex_data['rot_0'])
    qx = np.array(vertex_data['rot_1'])
    qy = np.array(vertex_data['rot_2'])
    qz = np.array(vertex_data['rot_3'])
    
    #format scipy
    quats_scipy = np.vstack((qx, qy, qz, w)).T
    r_splats = Rotation.from_quat(quats_scipy)
    
    # Application de la rotation globale aux splats
    r_new = r_global * r_splats 
    new_quats = r_new.as_quat() # Retour en (x, y, z, w)
    
    # On remet les valeurs à jour dans vertex_data (en format w, x, y, z)
    vertex_data['rot_0'] = new_quats[:, 3] # w
    vertex_data['rot_1'] = new_quats[:, 0] # x
    vertex_data['rot_2'] = new_quats[:, 1] # y
    vertex_data['rot_3'] = new_quats[:, 2] # z
    # ==========================================

    # Couleurs (Conversion DC vers RGB puis HSV)
    SH_C0 = 0.28209479177387814
    r = np.clip(vertex_data['f_dc_0'] * SH_C0 + 0.5, 0, 1)
    g = np.clip(vertex_data['f_dc_1'] * SH_C0 + 0.5, 0, 1)
    b = np.clip(vertex_data['f_dc_2'] * SH_C0 + 0.5, 0, 1)
    h, s, v = rgb_to_hsv(r, g, b)

    # ==========================================
    # 1. ISOLER LES ARUCO (Turquoise)
    # ==========================================
    mask_aruco = (h > 150) & (h < 195) & (s > 0.1) & (v > 0.1)
    aruco_indices = np.where(mask_aruco)[0]
    
    if len(aruco_indices) < 100:
        raise ValueError("Pas assez de points turquoise trouvés pour les ArUco.")
        
    pcd_aruco = o3d.geometry.PointCloud()
    pcd_aruco.points = o3d.utility.Vector3dVector(np.vstack((x[aruco_indices], y[aruco_indices], z[aruco_indices])).T)
    
    labels_aruco = np.array(pcd_aruco.cluster_dbscan(eps=1, min_points=100, print_progress=False))
    unique_labels, counts = np.unique(labels_aruco[labels_aruco >= 0], return_counts=True)
    
    if len(unique_labels) < 4:
        raise ValueError(f"Seulement {len(unique_labels)} clusters ArUco trouvés (4 attendus).")
        
    top_4_labels = unique_labels[np.argsort(counts)[-4:]]
    centroids = []
    for lbl in top_4_labels:
        cluster_points = np.asarray(pcd_aruco.points)[labels_aruco == lbl]
        centroids.append(np.mean(cluster_points, axis=0))
    centroids = np.array(centroids)

    # Calcul de l'envergure sur X et Y
    span_x = np.max(centroids[:, 0]) - np.min(centroids[:, 0])
    span_y = np.max(centroids[:, 1]) - np.min(centroids[:, 1])
    
    # Assigner les dimensions de la feuille
    if span_x > span_y:
        scale_x = 0.25 / span_x  # X est la longueur
        scale_y = 0.164 / span_y  # Y est la largeur
    else:
        scale_x = 0.164 / span_x  # X est la largeur
        scale_y = 0.25 / span_y  # Y est la longueur
        
    print(f"Échelle X calculée : {scale_x:.4f}")
    print(f"Échelle Y calculée : {scale_y:.4f}")
    """
    # ==========================================
    # 2. ISOLER LE CUBE (Bleu Ciel)
    # ==========================================
    #scale_z= 0.025/extract_scale_cube.find_blue_cube_and_scale(input_ply=input_ply)[2]
    #scale_z = 0.025 / 0.556774 # mesuré à la main
    scale_z=(scale_x+scale_y)/2
    print(f"échelle trouvée en z = {scale_z:.4f}")
    """

    # ==========================================
    #2. Scale graçe aux postions des cameras par rapport au tray ( dont le z correspond au centre des arucos)
    #=========================================
    scale_z=0.320/np.mean(centroids[:,2])

    # ==========================================
    # 3. APPLIQUER LA MISE À L'ÉCHELLE (X, Y, Z séparés)
    # ==========================================
    x_scaled = x * scale_x
    y_scaled = y * scale_y
    z_scaled = z * scale_z

    avg_scale = (scale_x + scale_y + scale_z) / 3.0
    scale_names = [p.name for p in plydata.elements[0].properties if p.name.startswith('scale_')]
    for name in scale_names:
        vertex_data[name] += np.log(avg_scale) 

    # ==========================================
    # 4. TRANSLATION (Recentrer au milieu des ArUco, à Z=0.320)
    # ==========================================
    new_centroids = centroids.copy()
    new_centroids[:, 0] *= scale_x
    new_centroids[:, 1] *= scale_y
    new_centroids[:, 2] *= scale_z
    
    center_of_aruco = np.mean(new_centroids, axis=0)
    print(f"Centre actuel du plateau (après scale) : {center_of_aruco}")
    
    x_final = x_scaled - center_of_aruco[0]
    y_final = y_scaled - center_of_aruco[1]
    z_final = (z_scaled - center_of_aruco[2]) + 0.320
    
    print("Translation vers l'axe de la caméra (0, 0, 0.320) effectuée.")

    # ==========================================
    # 5. SAUVEGARDE
    # ==========================================
    vertex_data['x'] = x_final
    vertex_data['y'] = y_final
    vertex_data['z'] = z_final

    new_element = PlyElement.describe(vertex_data, 'vertex')
    PlyData([new_element], text=False).write(output_ply)
    print(f"Fichier final sauvegardé : {output_ply}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True, help="PLY original")
    parser.add_argument("--output", type=str, required=True, help="PLY mis à l'échelle et déplacé")
    parser.add_argument("--rot", default=np.array([+3.2, +0.8, 0.0]) , help="Array contenant les rotations (Pitch, Yaw, Roll) en degrés, séparées par des virgules. Exemple : 3.2,0.8,0.0")
    args = parser.parse_args()
    args = parser.parse_args()
    
    
    # mesuré à la main
    process_and_align(args.input, args.output, args.rot)