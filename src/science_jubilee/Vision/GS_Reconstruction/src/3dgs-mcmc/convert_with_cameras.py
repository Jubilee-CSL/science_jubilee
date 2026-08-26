#
# Copyright (C) 2023, Inria
# GRAPHDECO research group, https://team.inria.fr/graphdeco
# All rights reserved.
#

import logging
import os
import shutil
import re
import numpy as np
import cv2
import ast
from argparse import ArgumentParser
from scipy.spatial.transform import Rotation as R

# This Python script is based on the shell converter script provided in the MipNerF 360 repository.
parser = ArgumentParser("Colmap converter")
parser.add_argument("--no_gpu", action='store_true')
parser.add_argument("--skip_matching", action='store_true')
parser.add_argument("--source_path", "-s", required=True, type=str)
parser.add_argument("--camera", default="OPENCV", type=str)
parser.add_argument("--colmap_executable", default="", type=str)
parser.add_argument("--resize", action="store_true")
parser.add_argument("--magick_executable", default="", type=str)
parser.add_argument("--prior_cam_config", default=None, type=str)
args = parser.parse_args()

colmap_command = '"{}"'.format(args.colmap_executable) if len(args.colmap_executable) > 0 else "colmap"
magick_command = '"{}"'.format(args.magick_executable) if len(args.magick_executable) > 0 else "magick"
use_gpu = 1 if not args.no_gpu else 0

# ==============================================================================
# CONFIGURATION DE LA CAMÉRA (JUBILEE)
# ==============================================================================
cam_config = {
    'cx': 961.2134486884058,
    'cy': 538.5647691981069,
    'dist': [
        -0.052024740428130545, 
        0.5822565858991794, 
        0.00019694752077129167, 
        -0.0005687317259763694, 
        -1.2161810267808781
    ],
    'fx': 1467.553917032269,
    'fy': 1476.7692142590815,
    'offset': [0, -20, 0]
}

# Si on passe la config via le bash, on l'évalue proprement en dictionnaire
if args.prior_cam_config is not None:
    print("✅ Configuration caméra personnalisée détectée.")
    cam_config = ast.literal_eval(args.prior_cam_config)

# Paramètres formatés pour COLMAP
fx, fy = cam_config['fx'], cam_config['fy']
cx, cy = cam_config['cx'], cam_config['cy']
k1, k2, p1, p2 = cam_config['dist'][0], cam_config['dist'][1], cam_config['dist'][2], cam_config['dist'][3]
colmap_camera_params = f"{fx},{fy},{cx},{cy},{k1},{k2},{p1},{p2}"


if not args.skip_matching:
    os.makedirs(args.source_path + "/distorted/sparse", exist_ok=True)

    ## Feature extraction (AVEC LES PARAMETRES DE LA LENTILLE FORCÉS)
    print("Extraction des features avec les paramètres OpenCV forcés...")
    feat_extracton_cmd = colmap_command + " feature_extractor "\
        "--database_path " + args.source_path + "/distorted/database.db \
        --image_path " + args.source_path + "/input \
        --ImageReader.single_camera 1 \
        --ImageReader.camera_model OPENCV \
        --ImageReader.camera_params " + colmap_camera_params + " \
        --SiftExtraction.use_gpu " + str(use_gpu)
    exit_code = os.system(feat_extracton_cmd)
    if exit_code != 0:
        logging.error(f"Feature extraction failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ## Feature matching
    feat_matching_cmd = colmap_command + " exhaustive_matcher \
        --database_path " + args.source_path + "/distorted/database.db \
        --SiftMatching.use_gpu " + str(use_gpu)
    exit_code = os.system(feat_matching_cmd)
    if exit_code != 0:
        logging.error(f"Feature matching failed with code {exit_code}. Exiting.")
        exit(exit_code)

    ## Bundle adjustment (Mapper classique pour générer les points !)
    print("Démarrage du Mapper (Génération du nuage de points complet)...")
    mapper_cmd = (colmap_command + " mapper \
        --database_path " + args.source_path + "/distorted/database.db \
        --image_path "  + args.source_path + "/input \
        --output_path "  + args.source_path + "/distorted/sparse \
        --Mapper.ba_global_function_tolerance=0.000001")
    exit_code = os.system(mapper_cmd)
    if exit_code != 0:
        logging.error(f"Mapper failed with code {exit_code}. Exiting.")
        exit(exit_code)

    # ==============================================================================
    # AJOUT : CONVERSION DU MODÈLE BINAIRE EN TEXTE POUR PYTHON
    # ==============================================================================
    print("Conversion des fichiers binaires COLMAP en fichiers texte...")
    sparse_0 = args.source_path + "/distorted/sparse/0"
    converter_cmd = (colmap_command + f" model_converter \
        --input_path {sparse_0} \
        --output_path {sparse_0} \
        --output_type TXT")
    os.system(converter_cmd)
    # ==============================================================================
    # NOUVEAU : TRIANGULATION FORCÉE (ÉCRASEMENT DES POSES PAR JUBILEE)
    # ==============================================================================
    print("Écrasement des poses par les coordonnées Jubilee (Triangulation forcée)...")
    sparse_0 = args.source_path + "/distorted/sparse/0"
    forced_path = args.source_path + "/distorted/sparse/0_forced"
    os.makedirs(forced_path, exist_ok=True)

    # 1. Copier le modèle de caméra
    shutil.copy2(os.path.join(sparse_0, "cameras.txt"), os.path.join(forced_path, "cameras.txt"))

    # 2. Créer un fichier de points 3D totalement vide
    with open(os.path.join(forced_path, "points3D.txt"), "w") as f:
        f.write("# 3D point list with one line of data per point:\n")

    # 3. Réécrire images.txt avec tes poses, MAIS en conservant les points 2D du Mapper !
    R_c2w = R.from_euler('x', 180, degrees=True).as_matrix()

    with open(os.path.join(sparse_0, "images.txt"), "r") as f_in:
        lines = f_in.readlines()

    valid_images_count = 0
    with open(os.path.join(forced_path, "images.txt"), "w") as f_out:
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith("#"):
                f_out.write(line)
                i += 1
                continue

            # C'est une ligne de caméra : IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME
            parts = line.strip().split()
            if len(parts) >= 10:
                image_id = parts[0]
                camera_id = parts[8]
                filename = parts[9]

                # Extraction depuis ton nouveau format img_n1_x...
                match = re.search(r'img_n\d+_x(-?\d+)_y(-?\d+)_z(-?\d+)', filename)
                if match:
                    valid_images_count += 1
                    x_m = float(match.group(1)) / 100.0
                    y_m = float(match.group(2)) / 100.0
                    z_m = float(match.group(3)) / 100.0

                    T_c2w = np.array([x_m, y_m, z_m])
                    R_w2c = R_c2w.T
                    T_w2c = -np.dot(R_w2c, T_c2w)
                    quat_w2c = R.from_matrix(R_w2c).as_quat()
                    qw, qx, qy, qz = quat_w2c[3], quat_w2c[0], quat_w2c[1], quat_w2c[2]

                    new_line = f"{image_id} {qw} {qx} {qy} {qz} {T_w2c[0]} {T_w2c[1]} {T_w2c[2]} {camera_id} {filename}\n"
                    f_out.write(new_line)
                else:
                    f_out.write(line) # Sécurité si le nom ne matche pas

                # Ligne suivante : Les points 2D qu'il faut garder pour la triangulation
                i += 1
                points2d = lines[i].strip().split()
                
                # Le format est : X Y POINT3D_ID X Y POINT3D_ID...
                # On remplace tous les identifiants 3D (chaque 3ème élément) par -1
                for j in range(2, len(points2d), 3):
                    points2d[j] = "-1"
                    
                # On réécrit la ligne modifiée
                f_out.write(" ".join(points2d) + "\n")
            i += 1

    print(f"✅ {valid_images_count} poses écrasées avec succès !")

    # 4. Lancer la triangulation avec les poses parfaites
    print("Génération du nuage de points 3D définitif...")
    triangulated_path = args.source_path + "/distorted/sparse/0_final"
    os.makedirs(triangulated_path, exist_ok=True)

    triangulator_cmd = (colmap_command + f" point_triangulator \
        --database_path {args.source_path}/distorted/database.db \
        --image_path {args.source_path}/input \
        --input_path {forced_path} \
        --output_path {triangulated_path}")
    
    os.system(triangulator_cmd)

    # 5. Remplacer le faux modèle de départ par notre modèle parfait
    shutil.rmtree(sparse_0)
    shutil.move(triangulated_path, sparse_0)
    # ==============================================================================

### Image undistortion
## We need to undistort our images into ideal pinhole intrinsics.
img_undist_cmd = (colmap_command + " image_undistorter \
    --image_path " + args.source_path + "/input \
    --input_path " + args.source_path + "/distorted/sparse/0 \
    --output_path " + args.source_path + "\
    --output_type COLMAP")
exit_code = os.system(img_undist_cmd)
if exit_code != 0:
    logging.error(f"Image undistortion failed with code {exit_code}. Exiting.")
    exit(exit_code)

files = os.listdir(args.source_path + "/sparse")
os.makedirs(args.source_path + "/sparse/0", exist_ok=True)
# Copy each file from the source directory to the destination directory
for file in files:
    if file == '0':
        continue
    source_file = os.path.join(args.source_path, "sparse", file)
    destination_file = os.path.join(args.source_path, "sparse", "0", file)
    shutil.move(source_file, destination_file)

if(args.resize):
    print("Copying and resizing...")

    # Resize images.
    os.makedirs(args.source_path + "/images_2", exist_ok=True)
    os.makedirs(args.source_path + "/images_4", exist_ok=True)
    os.makedirs(args.source_path + "/images_8", exist_ok=True)
    files = os.listdir(args.source_path + "/images")
    for file in files:
        source_file = os.path.join(args.source_path, "images", file)

        destination_file = os.path.join(args.source_path, "images_2", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 50% " + destination_file)

        destination_file = os.path.join(args.source_path, "images_4", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 25% " + destination_file)

        destination_file = os.path.join(args.source_path, "images_8", file)
        shutil.copy2(source_file, destination_file)
        exit_code = os.system(magick_command + " mogrify -resize 12.5% " + destination_file)

print("Done.")