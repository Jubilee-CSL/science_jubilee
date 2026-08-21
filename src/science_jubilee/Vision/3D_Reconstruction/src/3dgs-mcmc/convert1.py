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
    # NOUVEAU : ALIGNEMENT PHYSIQUE SUR LES AXES JUBILEE
    # ==============================================================================
    print("Mise à l'échelle et alignement avec les coordonnées Jubilee...")
    input_images_path = args.source_path + "/input"
    image_files = [f for f in os.listdir(input_images_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]

    ref_path = args.source_path + "/distorted/ref_images.txt"
    valid_images_count = 0
    with open(ref_path, "w") as f:
        for filename in image_files:
            match = re.search(r'img_x(-?\d+)_y(-?\d+)_z(-?\d+)', filename)
            if match:
                valid_images_count += 1
                x_m = float(match.group(1)) / 100.0
                y_m = float(match.group(2)) / 100.0
                z_m = float(match.group(3)) / 100.0
                # Format: image_name X Y Z
                f.write(f"{filename} {x_m} {y_m} {z_m}\n")

    if valid_images_count > 0:
        # On redresse le modèle "0" fraîchement créé par le mapper
        sparse_0_path = args.source_path + "/distorted/sparse/0"
        aligner_cmd = (colmap_command + f" model_aligner \
            --input_path {sparse_0_path} \
            --output_path {sparse_0_path} \
            --ref_images_path {ref_path} \
            --robust_alignment 1 \
            --robust_alignment_max_error 0.05")
        
        exit_code = os.system(aligner_cmd)
        if exit_code == 0:
            print(f"✅ Modèle parfaitement aligné et mis à l'échelle de la machine Jubilee ({valid_images_count} positions utilisées) !")
        else:
            print("⚠️ Attention, l'alignement Jubilee a échoué. On garde l'échelle COLMAP par défaut.")
    else:
        print("⚠️ Aucune coordonnée xyz trouvée dans les noms des images. Alignement ignoré.")
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