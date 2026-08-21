#!/bin/bash

set -e

#Theses are default values of the directories, you must change the Project_dir to your path into 3d_reconstruction folder
PROJECT_DIR="/mnt/c/Users/Justin/Desktop/Jubilee/science_jubilee/src/science_jubilee/Vision/3d_reconstruction"
DATASET_PATH="$PROJECT_DIR/Datasets/latest_dataset"


#You can also call the .sh file with arguments so it change the
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dataset) DATASET_PATH="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;

    esac
    shift
done


echo "=========================================="
echo " DÉBUT DU PIPELINE DE RECONSTRUCTION 3D"
echo "=========================================="
echo " Dossier projet  : $PROJECT_DIR"
echo " Dossier dataset : $DATASET_PATH"
echo "=========================================="


# 1. Conda environement activation; You can change this if you are not using miniconda3 and if you have call the wsl environement differently
echo " Activation de l'environnement Conda (gs_final)..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gaussian_splatting_inria

#Colmap training for sparse points and camera pose estimation
echo "Step 1/2 : Colmap sparse points"
cd "$PROJECT_DIR/src/3dgs-mcmc"
python convert1.py -s "$DATASET_PATH" 

echo "Colmap trained succesfully"