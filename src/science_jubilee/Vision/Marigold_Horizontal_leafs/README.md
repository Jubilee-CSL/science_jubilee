# Monocular Horizontal Leaves

This module detects approximately horizontal plant leaves from one Jubilee camera image. It combines tray and plant segmentation, monocular depth estimation, surface-normal estimation, 3D clustering, and conversion of selected image regions into camera-relative millimetre coordinates.

The recommended entry point is [`test_pipeline.ipynb`](test_pipeline.ipynb). It exposes the processing stages in separate cells so that masks, depth maps, normals, clusters, targets, and robot motion can be inspected independently. The reusable stages are exposed as Sacred ingredients in [`ingredients/`](ingredients/).

## 1. Architecture

```text
Marigold_Horizontal_leafs/
├── config.yaml                         # camera, physical, and filtering values
├── input/                              # captured or offline input images
├── output/                             # intermediate and final outputs
├── output_3d/                          # optional Open3D reconstruction outputs
├── ingredients/
│   ├── filter_scene.py                 # ArUco tray and HSV plant/cube masks
│   ├── inference_marigold.py           # Marigold depth and normal inference
│   ├── inference_MoGe.py               # optional MoGe depth and normal inference
│   ├── target_horizontals.py            # Sacred target-detection ingredient
│   ├── extract_leafs.py                # Open3D plant/leaf clustering helpers
│   ├── reconstruction.py               # optional point-cloud/mesh generation
│   └── pipeline.py                     # NOT FINISHED Sacred orchestration
├── src/
│   ├── segment_and_target.py            # legacy command-line pipeline
│   ├── inference_marigold.py            # legacy direct Marigold command
│   ├── jubilee_horizontal_target.py     # legacy hardware entry point
│   └── 3d_reconstruction.py             # legacy reconstruction entry point
├── test_pipeline.ipynb                 # recommended step-by-step workflow
└── README.md
```

## 2. Requirements and installation

### 2.1 Windows and Python

The notebook is normally run from Windows in VS Code. A CUDA-capable NVIDIA GPU is strongly recommended for Marigold and required by the current MoGe implementation. CPU execution may work for Marigold, but it is substantially slower and the models still require significant memory.

```powershell
conda create -n Monocular_env python=3.10 -y
conda activate Monocular_env

conda install pytorch torchvision pytorch-cuda=11.8 -c pytorch -c nvidia -y
pip install sacred diffusers transformers accelerate omegaconf open_clip_torch `
    opencv-python numpy pillow pyyaml imageio matplotlib open3d `
    scikit-learn scikit-image
```

Select `monocular_env` as the Python interpreter and notebook kernel in VS Code. Verify the installation:

```powershell
python -c "import torch, cv2, numpy, open3d, sacred; print(torch.cuda.is_available())"
```

The first Marigold run downloads `prs-eth/marigold-depth-v1-1` and `prs-eth/marigold-normals-v1-1`. It requires internet access and can take several minutes. Later runs use the local Hugging Face cache.

### 2.2 MoGe installation

MoGe is an alternative to Marigold. The code imports `moge.model.v2` and loads `Ruicheng/moge-2-vitl-normal` on CUDA.

Install MoGe with `pip install -e . --index-url https://download.pytorch.org/whl/cu130` in the same environment, then verify:

```powershell
python -c "from moge.model.v2 import MoGeModel; print('MoGe import OK')"
```

MoGe is not required if uyou use the Marigold path. Its current implementation creates `torch.device("cuda")` directly, so a CUDA GPU is required for this path.

### 2.3 Jubilee hardware

Hardware acquisition additionally requires the normal `science_jubilee` machine environment, a reachable Jubilee controller, a configured `.env.hardware` file, and a camera tool registered with `MachineSession`. Use `hardware = False` in the notebook for offline development.

## 3. Camera calibration and physical reference

The camera parameters uses the `camera` object from MachineAgency passed by the caller. That object supplies `camera.K` and `camera.dist`.

Theses values are stocked automatically as a camera.yaml on the Calibration directory, you may follow its instructions before using the Monocular Horizontal leaves

Theses valueas are used for the pinhole model after OpenCV undistortion:

```text
x = x_normalized * z
y = y_normalized * z
```

`xyz_mm` is camera-relative. It is not a global Jubilee coordinate until the camera offset and capture position are applied.

## 4. Recommended notebook workflow

Open [`test_pipeline.ipynb`](test_pipeline.ipynb) and run the cells in order.

### Step 1 - Imports and paths

The notebook searches upward for the repository root, adds `src/` and the repository root to `sys.path`, and creates `input/` and `output/latest/`.

| Variable | Meaning |
|---|---|
| `hardware` | `True` captures from Jubilee; `False` uses an offline image |
| `STEPS` | notebook setting for inference Marigold |
| `quality` | notebook setting for inference MoGe |
| `RUN_RECONSTRUCTION` | controls optional reconstruction work |
| `TARGET_AUTO` | selects a target automatically instead of manually |

### Step 2 - Capture an image

With hardware enabled, the camera is moved to:

```python
X_DEPART, Y_DEPART, Z_DEPART = 130.0, 150.0, 320.0
```

and the image is saved as `input/latest.jpg`. With hardware disabled, the notebook reuses an existing image such as `input/test.png` and does not move the machine.

### Step 3 - Segment the scene

`run_filter_scene` returns `tray_mask`, `plant_mask`, and `cube_mask`.

- The tray is the rectangle defined by detected `DICT_4X4_50` ArUco markers, dilated with a 20-pixel kernel.
- The plant mask uses HSV hue `35..95`, saturation/value at least `40`, and a `5x5` open/close morphology operation.
- The optional blue cube mask uses HSV hue `100..105`, saturation/value at least `100`, and the same morphology operation.

The current ingredient uses HSV segmentation. The older `rembg` fallback statement is not accurate for the current implementation.

### Step 4 - Estimate depth and normals

Marigold example:

```python
inference = run_infer_depths_and_normals(
    image=image,
    output_dir=str(OUTPUT_DIR),
    steps=1000,
    image_name=IMAGE_PATH.name,
)
depth_map = inference["depth"].squeeze()
normals = inference["normals"]
```

`steps` is the number of diffusion inference steps; higher values generally increase runtime.

MoGe alternative:

```python
inference = run_infer_depths_and_normals(
    image=image,
    output_dir=str(OUTPUT_DIR),
    image_name=IMAGE_PATH.name,
    resolution_level=10,
)
depth_map = inference["depth"]
normals = inference["normals"]
```

`resolution_level` controls MoGe inference resolution. Its function default is `9`; the notebook example uses `10`. MoGe also returns `3d_points`. Run one inference route at a time so `depth_map` and `normals` come from the same model.

### Step 5 - Detect horizontal targets

The target stage performs depth scaling, normal masking, morphology, spatial DBSCAN in 3D, a second DBSCAN on `normal_z`, area filtering, and projection of selected centroids into `xyz_mm`.

Typical call:

```python
targets_result = run_estimate_horizontal_targets(
    image=image,
    depth_map=depth_map,
    normals=normals,
    output_dir=str(OUTPUT_DIR),
    image_name=IMAGE_PATH.name,
    tray_z_mm=Z_DEPART,
    normal_threshold=0.94,
    min_area_px=2000,
    max_area_px=150000,
    cluster_eps_mm=1.8,
    cluster_eps_normal=0.1,
    camera=cam,
    plant_height=160,
    scale_cube=None,
)
```

The current notebook experiment keeps one valid normal subcluster per spatial leaf. If several are found, it keeps the one with the highest standard deviation of `normal_z`. Its representative pixel is a centroid weighted by `abs(normal_z)`, so the strongest horizontal-normal points have greater influence.

### Step 6 - Select a target

Set `TARGET_AUTO = True` to choose the target closest to the camera:

```python
target = max(targets, key=lambda item: -item["xyz_mm"][2])
```

Otherwise inspect the candidates and select one explicitly. Always check that `targets` is not empty.

### Step 7 - Move Jubilee to a target

The motion cell first moves to a safe Z, then moves in X/Y, and finally approaches the target Z. The final position combines the capture position, target `xyz_mm`, `cam.offset`, and the experiment-specific `supplementary_offset_xyz`. Validate the overlay before enabling hardware motion.

### Step 8 - Optional Open3D reconstruction

`run_create_point_cloud` can create a point cloud from `depth_mm`. Use `meshing=False` when only the point cloud is required. With meshing enabled, Open3D creates a mesh that can be inspected with `draw_geometries`.

## 5. Parameter reference

### 5.1 Target detection

The Sacred function is:

```python
run_estimate_horizontal_targets(
    image, depth_map, normals, tray_z_mm, normal_threshold,
    min_area_px, max_area_px, cluster_eps_mm, cluster_eps_normal,
    camera, plant_height, scale_cube, output_dir, image_name
)
```

| Parameter | Meaning |
|---|---|
| `image` | input image array |
| `depth_map` | relative depth prediction |
| `normals` | normal map; Z is `normals[:, :, 2]` |
| `tray_z_mm` | tray reference used for depth conversion |
| `normal_threshold` | minimum `abs(normal_z)` in the candidate mask |
| `min_area_px` | minimum candidate area |
| `max_area_px` | maximum candidate area |
| `cluster_eps_mm` | spatial DBSCAN radius in millimetres; units must match `XYZ_map` |
| `cluster_eps_normal` | DBSCAN radius for normal-Z similarity |
| `camera` | camera object supplying `K` and `dist` |
| `plant_height` | optional plant-based depth scaling |
| `scale_cube` | optional blue-cube calibration length |
| `output_dir` | directory for intermediate files |
| `image_name` | output naming stem |

When `scale_cube` is set, non-finite cube depths are removed and statistical outliers are rejected with the IQR rule before cube scaling. The retained cube values are used for calibration.

### 5.2 Segmentation constants

These values are coded in [`ingredients/filter_scene.py`](ingredients/filter_scene.py), can be changed directly to better fit your scene:

| Component | Current value |
|---|---|
| tray marker dictionary | `DICT_4X4_50` |
| tray padding | `20` pixels |
| plant HSV | hue `35..95`, saturation/value `40..255` |
| cube HSV | hue `100..105`, saturation/value `100..255` |
| plant/cube morphology | `5x5` kernel |
| candidate morphology | `3x3` kernel |

### 5.3 Open3D leaf clustering

`run_extract_leaf_clusters` voxel-downsamples with `voxel_size=0.005` and then runs Open3D DBSCAN.

| Parameter | Notebook value | Meaning |
|---|---:|---|
| `distance_threshold` | `0.0092` or `0.0095` | Open3D DBSCAN radius in the point-cloud unit |
| `min_points` | `20` | minimum points in a cluster |
| `size_threshold` | `1e-5` | minimum largest covariance eigenvalue |
| `shape_threshold` | `0.98` | upper bound on the eigenvalue ratio |
| `height_ratio` | `0.1` | minimum relative centroid height |

The notebook point cloud is divided by `1000` before this stage, so these values are interpreted in metres. Keep the radius and point-cloud unit consistent.

### 5.4 Reconstruction

The optional reconstruction function accepts `image`, `depth_mm`, `camera`, `output_dir`, `image_name`, `meshing`, `alpha`, and `decimate_ratio`. Smaller `alpha` values usually create tighter or more fragmented alpha-shape surfaces. The implementation uses fixed statistical filtering values `nb_neighbors=20` and `std_ratio=2.0`.

## 6. Outputs

The notebook normally writes to `output/latest/`:

```text
<stem>.jpg                  # image copied for inference
<stem>_depth.npy            # relative depth prediction
<stem>_normals.npy          # normal prediction
<stem>_input.jpg            # ingredient input image
<stem>_overlay.png          # detected-target overlay, when saved
<stem>_depth_mm.npy         # scaled depth, when saved
<stem>_tray_mask.png        # tray mask, when saved
<stem>_plant_mask.png       # plant mask, when saved
<stem>_targets.json         # target dictionaries, when saved
```

Targets contain `id`, `pixel`, `area_px`, `bbox`, `normal_confidence`, `depth_std_mm`, `xyz_mm`, and `normal`. Optional reconstruction can produce `<stem>_point_cloud.ply` and `<stem>_mesh.ply`.


## 7. Sacred ingredients

| Ingredient | Function | Role |
|---|---|---|
| `filter_scene` | `run_filter_scene` | tray, plant, and cube masks |
| `inference_marigold` | `run_infer_depths_and_normals` | Marigold inference |
| `inference_MoGe` | `run_infer_depths_and_normals` | MoGe depth, normals, and 3D points |
| `target_horizontals` | `run_estimate_horizontal_targets` | target detection and projection |
| `extract_leafs` | `run_extract_leaf_clusters` | Open3D spatial clustering |
| `reconstruction` | `run_create_point_cloud` | optional point-cloud and mesh generation |

Functions decorated with `@ingredient.capture` can receive configured values through Sacred. If a notebook call raises `SignatureError`, restart the kernel and rerun the imports so the current module signatures are loaded.

## 10. Troubleshooting

### Marigold dependencies or CUDA

Check the selected interpreter:

```powershell
python -c "import torch, diffusers, transformers, accelerate; print(torch.__version__, torch.cuda.is_available())"
```

For GPU out-of-memory errors, use fewer inference steps, close other GPU applications, or run Marigold on CPU. MoGe currently requires CUDA.

### No ArUco markers

The tray mask is empty when the expected `DICT_4X4_50` markers are not visible. Check the reference sheet, lighting, camera framing, and image colour conversion. Tray-based scaling is unreliable without this mask.

### No plant or cube pixels

Inspect the HSV masks. Their thresholds are hard-coded in `ingredients/filter_scene.py`; changing `config.yaml` does not change them.

### DBSCAN uses too much memory

Keep the point cloud downsampled, use a radius in the same unit as `XYZ_map`, and keep scikit-learn DBSCAN at `n_jobs=1`. A millimetre/metre mismatch can connect most of the scene and create a very large neighbour search.

### Empty-label reduction error

Manual label statistics must skip labels with no pixels before calling `x_idx.min()` or `y_idx.min()`. The notebook experiment contains this guard.

### Unexpected target coordinates

Check the inference model, camera matrix, distortion coefficients, depth scaling mode, camera offsets, and the sign convention used to convert camera coordinates to Jubilee coordinates. Inspect the overlay before moving the machine.

### Sacred `SignatureError`

Restart the notebook kernel and rerun the import cell. Compare the call with the signature in the currently imported ingredient file.

## 11. Practical recommendations

- Run offline with `hardware=False` before connecting Jubilee.
- Validate tray, plant, cube, depth, and normal visualizations independently.
- Tune area, normal, and DBSCAN thresholds one parameter group at a time.
- Keep `cluster_eps_mm` and `XYZ_map` units consistent.
- Record calibration, plant height, cube size, and inference model with every experiment.
- Use a unique output directory for results that must be compared later.
- Never enable automatic motion until the target overlay and coordinates have been checked.

## 12. Current status

The step-by-step notebook is the preferred development and debugging interface. The CLI and Jubilee script are useful legacy entry points, but they do not expose exactly the same segmentation, scaling, clustering, or filtering behaviour as the current Sacred notebook workflow. The calibration script mentioned by older documentation is not currently present in this directory.
