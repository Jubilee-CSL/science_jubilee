# GS Reconstruction

This module converts a sequence of images captured by the Jubilee camera into a 3D representation and then into an OBJ mesh. It combines:

1. image acquisition on an X/Y/Z grid;
2. camera-pose estimation and sparse point-cloud reconstruction with COLMAP;
3. MCMC 3D Gaussian Splatting training;
4. filtering of Gaussians that do not belong to the plant;
5. point-cloud scaling and alignment;
6. mesh generation with an alpha shape.

The recommended entry point is [`test_pipeline.ipynb`](test_pipeline.ipynb), which runs each stage in a separate cell. The individual stages are exposed as Sacred ingredients in [`ingredients/`](ingredients/).

## 1. Architecture

```text
GS_Reconstruction/
├── Datasets/
│   └── <dataset_name>/
│       ├── input/              # raw camera images
│       ├── images/             # images prepared by COLMAP
│       ├── sparse/             # COLMAP reconstruction
│       └── ...                 # camera files and metadata
├── Outputs/
│   └── <dataset_name>_results/
│       ├── 3d_reconstruction/
│       │   ├── cameras.json
│       │   └── point_cloud/
│       │       └── iteration_<N>/point_cloud.ply
│       ├── point_cloud_scaled.ply
│       └── mesh.obj
├── ingredients/
│   ├── colmap.py               # COLMAP conversion
│   ├── pre_process.py          # image filtering
│   ├── reconstruction.py       # Gaussian Splatting training
│   ├── post_process.py         # Gaussian point-cloud filtering
│   ├── scaling.py              # camera-based scaling
│   ├── meshing.py              # point cloud to OBJ
│   └── pipeline.py             # legacy Sacred orchestration
├── src/
│   ├── run_colmap.sh
│   ├── run_reconstruction.sh
│   ├── 3dgs-mcmc/              # training code
│   ├── filter_scene.py
│   ├── filter_plants.py
│   ├── scale_by_cameras.py
│   └── meshing.py
└── test_pipeline.ipynb          # recommended step-by-step pipeline
```

## 2. Requirements

### 2.1 Windows and WSL

The COLMAP and reconstruction stages run in WSL. Windows is mainly used for:

- storing the repository and image files;
- running VS Code and the notebook;
- communicating with Jubilee during acquisition;
- optionally running the SIBR viewer.

WSL must be able to access the repository through a `/mnt/<drive>/...` path. For example:

```bash
cd /mnt/c/Users/Justin/Desktop/Jubilee/science_jubilee
```

Check that WSL, Bash, Conda, and CUDA are available:

```bash
conda --version
nvidia-smi
wsl
bash --version #inside wsl
```

### 2.2 WSL Conda environment

The Bash scripts use the `gaussian_splatting_inria` environment by default and load Conda from:

```bash
~/miniconda3/etc/profile.d/conda.sh
```

Change these values in `src/run_colmap.sh` and `src/run_reconstruction.sh` if Miniconda is installed elsewhere or the environment has a different name.

Indicative environment setup:


```bash

conda create -y -n gaussian_splatting_inria python=3.8
conda activate gaussian_splatting_inria

conda install -c conda-forge colmap
conda install -c conda-forge gxx_linux-64=11
conda install -c nvidia cuda-nvcc=11.8 cuda-toolkit=11.8
conda install -c conda-forge libxcrypt

pip install plyfile tqdm
```
Install a pytorch version compatible with your cuda version: https://learn.microsoft.com/fr-fr/windows/ai/windows-ml/tutorials/pytorch-analysis-installation
```

cd science_jubilee/src/science_jubilee/Vision/GS_Reconstruction/src/3dgs-mcmc
pip install submodules/diff-gaussian-rasterization
pip install submodules/simple-knn
```

PyTorch and CUDA versions must be compatible with the GPU and the compiled extensions. For CUDA errors, first check the active environment and `torch.cuda.is_available()`.

### 2.3 Notebook Python environment

Open the jupyter notebook
The notebook uses the Python environment selected in VS Code. It must provide at least the libraries used by the modules: `sacred`, `numpy`, `matplotlib`, `opencv-python`, `open3d`, `plyfile`, `scipy`, and the segmentation dependencies.

The notebook automatically adds `src/` and the repository root to `sys.path`.

## 3. Jubilee acquisition

Acquisition is implemented by [`run_scan`](../../scripts/ingredients/snake_scan.py). It uses `MachineSession`, `FreeNavigator`, and the camera acquisition ingredient.

### Parameters

`run_scan` expects:

| Parameter | Format | Description |
|---|---|---|
| `start` | `[x, y, z]` | starting corner in mm |
| `stop` | `[x, y, z]` | opposite corner in mm |
| `steps` | `[nx, ny, nz]` | number of positions on each axis |
| `delay` | number | delay in seconds before each image |
| `out` | path | JPG output directory |

Positions are interpolated between `start` and `stop`, including both endpoints. For every Z layer, the scanner traverses X and Y in a serpentine pattern: adjacent Y passes are traversed in opposite directions. The physical position is stored in the filename:

```text
img_n<index>_x<X>_y<Y>_z<Z>.jpg
```

Example:

```text
img_n37_x180_y140_z240.jpg
```

The index starts at 1 and increases for every image. Files are written to `Datasets/<dataset_name>/input/`.

### Hardware example

In the notebook:

```python
hardware = True
dataset_name = "Latest_reconstruction"
start = [110.0, 80.0, 280.0]
stop = [250.0, 200.0, 220.0]
steps = [5, 5, 4]
delay = 2.0
```

With `hardware = False`, the notebook does not move the machine and reuses JPG files already present in `input/`.

## 4. Step-by-step pipeline

### Step 1 - Configuration

The configuration cell defines `dataset_name`, the `start` and `stop` bounds, the `steps` resolution, the acquisition delay, the training iteration count, and the dataset/output paths. The directories are created automatically.

### Step 2 - Snake scan

The cell calls `run_scan`. When `run_capture` is false, it only checks that JPG files exist in `images_dir`. This makes it possible to test reconstruction without a hardware connection.

### Step 3 - COLMAP

[`run_colmap.sh`](src/run_colmap.sh) calls `convert.py` from the `3dgs-mcmc` repository:

```bash
python convert.py -s <dataset_path>
```

This stage produces undistorted images and the SfM data required for training: camera poses, camera intrinsics, and a sparse point cloud.

In the notebook, verify the script path before calling it:

```python
colmap_script = REPO_ROOT / "src/science_jubilee/Vision/GS_Reconstruction/src/run_colmap.sh"
run_colmap(colmap_script=str(colmap_script), dataset_path=dataset_path)
```

### Step 4 - Image preprocessing

`run_filter_scene` calls `src/filter_scene.py`. It filters the background or tray to reduce Gaussians generated in irrelevant regions. The `use_ai` parameter enables or disables model-assisted segmentation.

```python
run_filter_scene(images_path=dataset_path / "images")
```

The default value of `use_ai` is configured in the `pre_process` ingredient.

### Step 5 - Gaussian Splatting training

[`run_reconstruction.sh`](src/run_reconstruction.sh) runs `train.py` in `src/3dgs-mcmc` with:

```bash
python train.py -s <dataset_path> \
    --init_type sfm \
    --cap_max 2000000 \
    --iterations <N> \
    --scale_reg 0.01 \
    --opacity_reg 0.01 \
    -m <output_path>
```

The main output is:

```text
<output_path>/point_cloud/iteration_<N>/point_cloud.ply
```

`iterations` must match in the script, the notebook, and the PLY path used by later stages.

### Step 6 - Gaussian filtering

`run_filter_plants` calls `src/filter_plants.py`. The filtering combines spatial bounds, Gaussian elongation, scale, opacity, local density, and saturation/value HSV thresholds.

The filtered PLY is usually written to:

```text
<output>/point_cloud/iteration_35000/point_cloud.ply
```

`iteration_35000` is a conventional output directory name. It does not mean that training must have run for 35,000 iterations.

#### `run_filter_plants` parameters

The ingredient configuration currently uses the following values:

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `input_ply` | `str` or `Path` | required | Input Gaussian Splatting point cloud. Usually `point_cloud/iteration_<N>/point_cloud.ply`. |
| `output_ply` | `str` or `Path` | required | Destination for the filtered point cloud. The parent directory must exist or be created by the caller. |
| `bbox_size` | `float` | `10000` | Size of the spatial bounding box used to remove points outside the reconstruction region. The effective unit must match the point-cloud coordinates. A very large value disables most bounding-box rejection. |
| `bbox_center` | `list[float]` | `[0.0, 2, 0.0]` | Center of the bounding box as `[x, y, z]`. It defines where the spatial filter is located. |
| `elongation_threshold` | `float` | `7.0` | Maximum accepted elongation ratio of a Gaussian. Values above this threshold are treated as elongated artifacts or floaters and removed. Lower values are stricter. |
| `scale_threshold` | `float` | `1` | Maximum accepted Gaussian scale according to the filtering implementation. Lower values remove more large or diffuse Gaussians. Confirm the coordinate/scale units before changing it. |
| `std_ratio` | `float` | `3` | Statistical-outlier threshold based on local-neighborhood distance. Lower values reject more points; higher values preserve more sparse geometry. |
| `opacity_threshold` | `float` | `0.07` | Minimum opacity accepted for a Gaussian. Points below this value are usually weak floaters or background noise and are removed. |
| `nb_neighbors` | `int` | `60` | Number of neighboring points used by local-density or statistical filtering. More neighbors produce a broader, more stable estimate but can remove small details. |
| `white_sat_thresh` | `float` | `0.55` | Saturation threshold used to identify low-color or white regions. Increasing it changes how aggressively pale/white Gaussians are rejected. |
| `white_val_thresh` | `float` | `0.2` | Value/brightness threshold used with the white-region filter. It controls which dark or low-value colors are considered during rejection. |

Example with all parameters explicit:

```python
filtered_ply = output_reconstruction / "point_cloud" / "iteration_35000" / "point_cloud.ply"

run_filter_plants(
    input_ply=input_ply,
    output_ply=filtered_ply,
    bbox_size=10000,
    bbox_center=[0.0, 2.0, 0.0],
    elongation_threshold=7.0,
    scale_threshold=1.0,
    std_ratio=3.0,
    opacity_threshold=0.07,
    nb_neighbors=60,
    white_sat_thresh=0.55,
    white_val_thresh=0.2,
)
```

#### How to tune the plant filter

Tune one parameter group at a time and inspect the resulting PLY after each run:

1. Start with `opacity_threshold` to remove transparent floaters.
2. Adjust `bbox_size` and `bbox_center` if points outside the tray or plant region remain.
3. Lower `elongation_threshold` to remove long artifacts, or increase it to preserve thin leaves.
4. Adjust `scale_threshold` when large blurred Gaussians dominate the output.
5. Change `nb_neighbors` and `std_ratio` together when the result contains isolated points.
6. Adjust `white_sat_thresh` and `white_val_thresh` only after checking the plant colors, because aggressive color filtering can remove pale leaves or highlights.

The best values depend on camera exposure, plant color, reconstruction scale, and COLMAP coverage. The defaults are a starting point, not universal physical constants.

### Step 7 - Scaling

`run_scale_by_cameras` reads the filtered PLY and `cameras.json`. It uses the camera positions to produce a scaled and oriented point cloud:

```text
<output>/point_cloud/iteration_35000/point_cloud_scaled.ply
```

`cameras_span` can receive known scene dimensions. Passing `None` uses the internal behavior of the module.

#### `run_scale_by_cameras` parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `input_ply` | `str` or `Path` | required | Filtered Gaussian point cloud to transform. |
| `output_ply` | `str` or `Path` | required | Destination for the aligned/scaled point cloud. |
| `cameras_json_path` | `str` or `Path` | required | `cameras.json` generated by the reconstruction stage. Camera names must correspond to the input dataset. |
| `cameras_span` | `list`, tuple, or `None` | `None` | Optional known scene span used to determine scale. `None` delegates scale estimation to `scale_by_cameras.py`. |

### Step 8 - Meshing

`run_meshing` calls `src/meshing.py` and builds an OBJ mesh using an alpha shape:

```python
run_meshing(
    input_ply=scaled_ply,
    output_obj=output_path / "mesh.obj",
)
```

The ingredient defaults are `alpha=0.0038` and `decimate_ratio=0.8`. A smaller alpha usually produces a stricter mesh; tune it according to the scale and density of the point cloud.

#### `run_meshing` parameters

| Parameter | Type | Default | Meaning |
|---|---|---:|---|
| `input_ply` | `str` or `Path` | required | Scaled point cloud used as the mesh source. |
| `output_obj` | `str` or `Path` | required | Destination OBJ file. |
| `alpha` | `float` | `0.0038` | Alpha-shape radius/control value. It determines which tetrahedral or surface connections are accepted. Smaller values create tighter, potentially fragmented meshes; larger values create more connected, potentially over-smoothed meshes. |
| `decimate_ratio` | `float` | `0.8` | Mesh simplification ratio passed to the meshing implementation. Keep it in the range expected by `src/meshing.py`; larger values generally preserve more triangles and smaller values simplify more aggressively. |

## 5. Function parameter reference

This section lists every public function used by the step-by-step notebook and the internal values that Sacred injects.

### `run_scan(start, stop, steps, delay, out)`

| Parameter | Type | Default/configuration | Meaning |
|---|---|---|---|
| `start` | `list[float]` | `[144.0, 125.0, 320.0]` | Starting `[X, Y, Z]` position in millimetres. |
| `stop` | `list[float]` | `[184.0, 145.0, 220.0]` | Ending `[X, Y, Z]` position in millimetres. |
| `steps` | `list[int]` | `[20, 10, 1]` | Number of samples along `[X, Y, Z]`. Each value must be at least `1`. |
| `delay` | `float` | `0.5` seconds | Sleep time before each capture. Increase it if the machine or lighting needs time to settle. |
| `out` | `str` or `Path` | required | Output folder. It is created automatically. |

The function calculates `step_x`, `step_y`, and `step_z` from the bounds and step counts. It returns a `list[str]` containing the saved JPG paths.

### `run_colmap(colmap_script, dataset_path)`

| Parameter | Type | Default/configuration | Meaning |
|---|---|---|---|
| `colmap_script` | `str` | repository `src/run_colmap.sh` | Windows path converted internally to a WSL path before invoking Bash. |
| `dataset_path` | `str` or `Path` | required | Dataset directory containing `input/`. The script writes COLMAP outputs into this dataset. |

The function returns a success string when the Bash process exits with code `0`; a non-zero exit code raises `RuntimeError`.

### `run_filter_scene(images_path, use_ai)`

| Parameter | Type | Default/configuration | Meaning |
|---|---|---|---|
| `images_path` | `str` or `Path` | required | Directory containing the COLMAP-prepared images to filter. |
| `use_ai` | `bool` | `True` | Selects AI-assisted segmentation in `src/filter_scene.py`. Set it to `False` to use the non-AI path supported by that implementation. |

The function returns `True` after `filter_scene.main` completes.

### `run_reconstruction(reconstruction_script, dataset_path, output_path, iterations)`

| Parameter | Type | Default/configuration | Meaning |
|---|---|---|---|
| `reconstruction_script` | `str` | repository `src/run_reconstruction.sh` | Windows path converted internally to WSL before invoking Bash. |
| `dataset_path` | `str` or `Path` | required | Dataset containing COLMAP input, camera, and sparse-reconstruction data. |
| `output_path` | `str` or `Path` | required | Model directory passed to `train.py` with `-m`. |
| `iterations` | `int` | `7000` | Number of Gaussian Splatting training iterations. This controls the expected `iteration_<N>` PLY directory. |

The function returns `True` when the training script exits successfully.

### `run_filter_plants(...)`

See the complete parameter table in [Step 6 - Gaussian filtering](#step-6---gaussian-filtering). All filter thresholds are Sacred-configured values and can be overridden explicitly in the notebook call.

## 6. Direct WSL execution

From WSL, the scripts can be run without the notebook:

```bash
cd /mnt/c/Users/Justin/Desktop/Jubilee/science_jubilee

bash src/science_jubilee/Vision/GS_Reconstruction/src/run_colmap.sh \
    --dataset /mnt/c/Users/Justin/Desktop/Jubilee/science_jubilee/src/science_jubilee/Vision/GS_Reconstruction/Datasets/Reconstruction_test

bash src/science_jubilee/Vision/GS_Reconstruction/src/run_reconstruction.sh \
    --dataset /mnt/c/Users/Justin/Desktop/Jubilee/science_jubilee/src/science_jubilee/Vision/GS_Reconstruction/Datasets/Reconstruction_test \
    --output /mnt/c/Users/Justin/Desktop/Jubilee/science_jubilee/src/science_jubilee/Vision/GS_Reconstruction/Outputs/Reconstruction_test_results/3d_reconstruction \
    --iterations 7000
```

Before execution, check:

```bash
bash -n src/science_jubilee/Vision/GS_Reconstruction/src/run_colmap.sh
bash -n src/science_jubilee/Vision/GS_Reconstruction/src/run_reconstruction.sh
test -d src/science_jubilee/Vision/GS_Reconstruction/src/3dgs-mcmc
```

## 7. Using Sacred ingredients

Each ingredient exposes a Sacred-captured function:

| Module | Function | Main arguments |
|---|---|---|
| `colmap.py` | `run_colmap` | `colmap_script`, `dataset_path` |
| `pre_process.py` | `run_filter_scene` | `images_path`, configured `use_ai` |
| `reconstruction.py` | `run_reconstruction` | `reconstruction_script`, `dataset_path`, `output_path`, `iterations` |
| `post_process.py` | `run_filter_plants` | input/output PLY paths and thresholds |
| `scaling.py` | `run_scale_by_cameras` | input/output PLY paths, `cameras_json_path`, `cameras_span` |
| `meshing.py` | `run_meshing` | input PLY, output OBJ, `alpha`, `decimate_ratio` |

With Sacred, a function decorated with `@ingredient.capture` can receive values from configuration. If an unexpected argument is passed, Sacred raises `SignatureError`. After editing an ingredient from a notebook, restart the kernel and rerun the import cell so the module is reloaded.

## 8. Troubleshooting

### `exit code 127` during COLMAP

This usually means that a command cannot be found in WSL. Check:

```bash
which bash
which python
conda env list
test -f src/science_jubilee/Vision/GS_Reconstruction/src/run_colmap.sh
```

Also check that `convert.py` exists in `src/3dgs-mcmc` and that the active environment contains its dependencies.

### `exit code 1` during training

The Python wrapper may not preserve the complete Bash output. Run `run_reconstruction.sh` directly in WSL to see the original error. Common causes include a missing or incorrectly named Conda environment, incompatible CUDA or PyTorch versions, uncompiled `diff-gaussian-rasterization` or `simple-knn` extensions, incomplete COLMAP data, invalid images, insufficient disk space, or insufficient VRAM.

### Sacred `SignatureError`

An `unexpected kwarg(s)` message means that the notebook call does not match the function signature currently loaded in the kernel. Restart the kernel, rerun the imports, and compare the call with the ingredient signature.

### Missing PLY `FileNotFoundError`

Check that training completed successfully, `iterations` matches the directory that was produced, `output_reconstruction` is the same path passed to `run_reconstruction`, and `point_cloud/iteration_<N>/point_cloud.ply` exists.

### Empty dataset

In offline mode, `run_scan` does not capture anything. It expects JPG files in `Datasets/<dataset_name>/input/`. If this directory is empty, the acquisition cell intentionally raises `FileNotFoundError`.

## 9. Optional SIBR viewer

The Windows viewer is not required to generate the PLY or mesh. If the binary is installed, launch it from its `bin` directory:

```powershell
SIBR_gaussianViewer_app.exe -m "C:\path\to\3d_reconstruction"
```

The model path must contain the Gaussian Splatting output, including `cameras.json` and the `point_cloud` directories.

## 10. Best practices

- Use a unique dataset name for every acquisition.
- Keep the original JPG files in `input/`.
- Start with a small number of positions and iterations to validate paths.
- Only start acquisition with `hardware=True` when the machine is connected.
- Run the WSL scripts directly when a Python wrapper hides the detailed error output.
- Check intermediate files after every stage before continuing.

## 11. Legacy pipeline status

`ingredients/pipeline.py` contains a global Sacred orchestration, but the step-by-step notebook is preferable for debugging and experimentation. The legacy pipeline still contains `3D_Reconstruction` paths that do not match the current directory layout and must be adapted before direct use.
