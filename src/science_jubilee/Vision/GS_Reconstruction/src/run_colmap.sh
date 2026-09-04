#!/bin/bash

set -e

# Resolve the project directory from this script so the path works on any clone.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
DATASET_PATH="$PROJECT_DIR/Datasets/latest_dataset"

# 1. Start with an empty string (meaning it defaults to False in Python)
DENSE_FLAG=""

# You can also call the .sh file with arguments so it changes the dataset or dense flag
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --dataset) DATASET_PATH="$2"; shift ;;
        
        # 2. If the user types --run_dense, we store the exact flag text.
        # Notice we removed the extra 'shift' here because it no longer takes a second value ($2).
        --run_dense) DENSE_FLAG="--run_dense" ;;
        
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

# Conda environment activation
echo " Activation de l'environnement Conda (gaussian_splatting_inria)..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate gaussian_splatting_inria

# Colmap training for sparse points and camera pose estimation
echo "Step 1/2 : Colmap sparse points"
cd "$PROJECT_DIR/src/3dgs-mcmc"

# 3. Pass the unquoted $DENSE_FLAG. 
python convert.py -s "$DATASET_PATH" $DENSE_FLAG

echo "Colmap trained successfully"