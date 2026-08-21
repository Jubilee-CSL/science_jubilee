#!/bin/bash

set -e

#Theses are default values of the directories, you must change the Project_dir to your path into 3d_reconstruction folder
PROJECT_DIR="/mnt/c/Users/Justin/Desktop/Jubilee/science_jubilee/src/science_jubilee/Vision/GS_Reconstruction"
DATASET_PATH="$PROJECT_DIR/Datasets/latest_dataset"
OUTPUT_DIR="$PROJECT_DIR/Outputs/latest_dataset_results"
ITERATIONS=10000

#You can also call the .sh file with arguments so it change the
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dataset) DATASET_PATH="$2"; shift ;;
        --output) OUTPUT_DIR="$2"; shift ;;
        --iterations) ITERATIONS="$2"; shift ;;
        *) echo "Unknown parameter: $1"; exit 1 ;;
    esac
    shift
done


echo "=========================================="
echo " DÉBUT DU PIPELINE DE RECONSTRUCTION 3D"
echo "=========================================="
echo " Dossier projet  : $PROJECT_DIR"
echo " Dossier dataset : $DATASET_PATH"
echo " Dossier sortie  : $OUTPUT_DIR"
echo " Itérations      : $ITERATIONS"
echo "=========================================="


mkdir -p "$OUTPUT_DIR"

# 1. Conda environement activation; You can change this if you are not using miniconda3 and if you have call the wsl environement differently
echo " Activation de l'environnement Conda (gs_final)..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gaussian_splatting_inria

#3DGS-mcmc training
cd "$PROJECT_DIR/src/3dgs-mcmc"
echo "Step 2/2 :Gaussian Splatting training"

python train.py -s "$DATASET_PATH" \
    --init_type sfm \
    --cap_max 2000000 \
    --iterations "$ITERATIONS" \
    --scale_reg 0.01 \
    --opacity_reg 0.01 \
    -m "$OUTPUT_DIR"

RAW_PLY="$OUTPUT_DIR/point_cloud/iteration_$ITERATIONS/point_cloud.ply"
echo "PLY file can be found here : $RAW_PLY"