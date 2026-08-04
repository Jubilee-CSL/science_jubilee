# Sur WSL (configuré avec miniconda et annexes basiques) acceder au fichier avec
$ cd /mnt/"ton/chemin/sur/windows/habituel"/3dgs-mcmc$

conda create -y -n gaussian_splatting python=3.8
conda activate gaussian_splatting

pip install plyfile tqdm torch==1.13.1+cu117 torchvision==0.14.1+cu117 torchaudio==0.13.1 --extra-index-url https://download.pytorch.org/whl/cu117
conda install cudatoolkit-dev=11.7 -c conda-forge


# 1. Compilateur C++ isolé
conda install -c conda-forge gxx_linux-64=11 -y

# 2. Compilateur CUDA (nvcc) et Toolkit de dev stables pour ton GPU
conda install -c nvidia cuda-nvcc=11.8 cuda-toolkit=11.8 -y

# 3. La bibliothèque de chiffrement pour Python (à la place d'apt)
conda install -c conda-forge libxcrypt -y

# 4. COLMAP pour l'alignement des caméras
    conda install -c conda-forge colmap -y



# export les chemins 

export CUDA_HOME=$CONDA_PREFIX
export CXX=x86_64-conda-linux-gnu-g++
export CC=x86_64-conda-linux-gnu-gcc
export PATH=$CUDA_HOME/bin:$PATH

# installation des sous modules

pip install submodules/diff-gaussian-rasterization
pip install submodules/simple-knn







Installation faite sur wsl pour plus de stabilitée et moins de conflit des verions 







### **Phase 1: Camera Poses and Sparse Point Cloud (COLMAP)**

Before splatting, we need the camera poses and a sparse 3D point cloud from your raw video or images.

* Place your images in a directory  `input/`.


* Use the `convert.py` script provided in the original `graphdeco-inria/gaussian-splatting` repository.

$ python convert.py -s <path_to_your_dataset_folder>

* This script acts as a wrapper for COLMAP to extract undistorted images and Structure-from-Motion (SfM) information.



### **Phase 2: Advanced Splatting (MCMC 3DGS)**

Since you noted that `ubc-vision/3dgs-mcmc` yields better results, we will use it for the optimization phase. This MCMC approach allows for a more optimal distribution of Gaussians.

* Initialize the training using the COLMAP point cloud by setting the `--init_type sfm` argument.


* Specify the maximum allowed number of Gaussians using the `--cap_max` argument.


* Apply the necessary regularizers by setting `--scale_reg 0.01` and `--opacity_reg 0.01` to maintain scene structure.


python train.py -s <path_to_your_dataset_folder> \
    --init_type sfm \
    --cap_max 2000000 \
    --scale_reg 0.01 \
    --opacity_reg 0.01 \
    -m <path_to_output_model_directory>


python train.py -s  /mnt/c/Users/Justin/Desktop/Jubilee/3d_reconstruction/input_data/Dataset_fake2_z320 \
    --init_type sfm \
    --cap_max 2000000 \
    --iterations 10000 \
    --scale_reg 0.01 \
    --opacity_reg 0.01 \
    -m /mnt/c/Users/Justin/Desktop/Jubilee/3d_reconstruction/output_data/Results_fake2_z320

### **Phase 3: Custom Filtering for Plants (Greenery & Density)**

Once the MCMC 3DGS training outputs the `.ply` file, we need a custom Python script (using a library like `plyfile`) to prune the data before meshing.

* **Color Filtering:** Gaussian base colors are stored as Spherical Harmonics (SH) DC terms (specifically the properties `f_dc_0`, `f_dc_1`, and `f_dc_2`). You will convert these back to RGB values and filter out any points that do not fall within your target "green" threshold to isolate the leaves.
* **Density Filtering:** Check the `opacity` property of each splat. Drop any Gaussians below a certain opacity threshold to remove floaters, background noise, and wispy artifacts.
* Save this filtered subset as a new `.ply` file.


 python filter_plants.py --input C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\3dgs_inria\point_cloud\iteration_10000\point_cloud0.ply--output C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\3dgs_inria\point_cloud\iteration_10000\point_cloud1.ply --bbox_size 17.0 --elongation_threshold 4.0 --scale_threshold 0.1  --std_ratio 1.5

recent call 

python filter_plants.py --input C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\3dgs-mcmc-output\point_cloud\iteration_10000\point_cloud0.ply --output C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\3dgs-mcmc-output\point_cloud\iteration_10000\point_cloud.ply --bbox_size 15 --bbox_y 2 --elongation_threshold 7.0 --scale_threshold 0.2 --std_ratio 3 --opacity_threshold 0.05 --nb_neighbors 40 --ban_hue_min 30  --ban_hue_max 60 --white_val_thresh 0.05 

recent call 
python filter_plants.py --input C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_vrai2\train_output\point_cloud\iteration_7000\point_cloud0.ply --output C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_vrai2\train_output\point_cloud\iteration_7000\point_cloud.ply --bbox_size 16 --bbox_y 2 --elongation_threshold 7.0 --scale_threshold 0.2 --std_ratio 3 --opacity_threshold 0.05 --nb_neighbors 40 --ban_hue_min 30  --ban_hue_max 60 --white_val_thresh 0.05 


### ** Optional gaussien viewer with SIBR_gaussianViewer app**

cd C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\src\viewers_windows\bin> 

SIBR_gaussianViewer_app.exe -m "Outpout_path"   

## Scaling the ply

python .\scale.py --input C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_vrai2\train_output\point_cloud\iteration_7000\point_cloud.ply --output C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_vrai2\train_output\point_cloud\point_cloud_scaled.ply                                                                                                                                 

## Messhing

python .\meshing.py --input C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_vrai2\train_output\point_cloud\iteration_7000\point_cloud_scaled.ply --output C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\gs_to_mesh\mesh_plant_2.obj --alpha 0.0049 --decimate 0.50                


## filter with 2.5d projection 

python .\proj_25d.py --input C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_fake2_z320\point_cloud\iteration_7000\point_cloud.ply --output C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\depth\ --cameras C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_fake2_z320\cameras.json --image_name 20260713_153523_112621.jpg -oi C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\input_data\Dataset_fake2_z320\input\20260713_153523_112621.jpg     





## Filter horizontal directly from gaussians

python .\track_horizontal_splats.py --input C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_fake2_z320\point_cloud\iteration_7000\point_cloud.ply --output C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\horizontauxv2\ --cameras C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_fake2_z320\cameras.json --image_name 20260713_153523_112621.jpg -oi C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\input_data\Dataset_fake2_z320\input\20260713_153523_112621.jpg     

                                        

## Filter using the mesh


python .\track_horizontal_mesh.py --input C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\gs_to_mesh\mesh_final.obj --output C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\horizontauxv3\ --cameras C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\output_data\Results_fake2_z320\cameras.json --image_name 20260713_153523_112621.jpg -oi C:\Users\Justin\Desktop\Jubilee\3d_reconstruction\input_data\Dataset_fake2_z320\input\20260713_153523_112621.jpg     