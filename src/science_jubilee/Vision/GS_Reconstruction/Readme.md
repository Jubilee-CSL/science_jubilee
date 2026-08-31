# GS Reconstruction

3D Gaussian Splatting pipeline for plant reconstruction on the Jubilee machine.

## Architecture

| Where | What runs there |
|-------|----------------|
| **Host** (pixi env) | JupyterLab, Sacred ingredients, `run_colmap` / `run_filter_scene` / `run_reconstruction` |
| **`colmap` container** | COLMAP feature extraction, matching, mapping, undistortion |
| **`gs` container** | BiRefNet background removal (`gs_preprocess` env), 3DGS-MCMC training (`gaussian_splatting_inria` env) |

The host notebook calls `docker compose run --rm <service> ...` for each GPU step — no shell scripts, no WSL.

## Two Docker services

### `colmap`
- Base: `colmap/colmap:20250530.2938` (CUDA 12.6, compatible with driver ≥ 520)
- Only runs `convert.py` (stdlib only, no pip packages)

### `gs`
- Base: `nvidia/cuda:11.7.1-devel-ubuntu20.04` (provides nvcc + headers at `/usr/local/cuda`)
- `gaussian_splatting_inria` env (Python 3.8): torch 1.13.1+cu117, CUDA extensions (`diff-gaussian-rasterization`, `simple-knn`), 3DGS-MCMC training
- `gs_preprocess` env (Python 3.10): torch 2.5.1+cu118, BiRefNet, open3d, Sacred ingredients

## Prerequisites

- Docker Desktop with GPU passthrough enabled
- NVIDIA driver ≥ 520 (CUDA 12.6 runtime)
- `nvidia-container-toolkit` installed

Verify GPU access:
```powershell
docker run --rm --gpus all nvidia/cuda:11.7.1-base-ubuntu20.04 nvidia-smi
```

## 1. Build images (once)

From the repo root:
```powershell
cd src\science_jubilee\Vision\GS_Reconstruction
docker compose build
```
Expect 30–60 min on first build (CUDA extensions compile from source).

## 2. Install host dependencies

```powershell
pip install -r src/science_jubilee/Vision/GS_Reconstruction/requirements.txt
```

## 3. Prepare your dataset

Place input images in:
```
GS_Reconstruction/Datasets/<scene_name>/input/
```

## 4. Run the pipeline

Open `test_pipeline.ipynb` in JupyterLab on the host and run cells in order:

| Cell | What it does | Runs in |
|------|-------------|---------|
| Config | Set `dataset_name`, `iterations` | host |
| Build | `docker compose build` | host → Docker |
| COLMAP | Feature extraction, matching, sparse reconstruction | `colmap` container |
| Filter scene | BiRefNet background removal | `gs` container |
| Train | 3DGS-MCMC Gaussian splatting | `gs` container |
| Filter Gaussians | Remove non-plant points | host |
| Scale & align | Camera-based scale recovery | host |
| Meshing | Alpha-shape mesh from point cloud | host |

## 5. Outputs

```
GS_Reconstruction/
├── Datasets/<scene>/
│   ├── input/          ← your source images
│   ├── images/         ← undistorted images (after COLMAP)
│   └── sparse/0/       ← COLMAP sparse reconstruction
└── Outputs/<scene>_results/
    └── 3d_reconstruction/
        └── point_cloud/iteration_<N>/
            ├── point_cloud.ply         ← raw Gaussians
            ├── point_cloud_scaled.ply  ← scaled + filtered
            └── mesh.obj                ← final mesh
```

## Troubleshooting

**COLMAP registers only a few images** — increase scan overlap, or check `distorted/sparse/` for multiple sub-reconstructions. The pipeline automatically picks the largest one.

**OOM during `docker compose build`** — increase Docker Desktop memory (Settings → Resources). The build cleans pip/conda caches inside each layer to reduce peak usage.

**`torch not compiled with CUDA`** — you ran a GPU step on the host; it must run inside the `gs` container via `docker compose run`.

exact target GPU, you can rebuild faster with e.g.
`docker build --build-arg TORCH_CUDA_ARCH_LIST="8.9" -t gs-reconstruction .`
— but the default should work regardless without needing to know that
ahead of time.

**Preprocess env — aruco detection and the segmentation model both load:**
```
docker run --rm --gpus all gs-reconstruction \
  conda run -n gs_preprocess python -c \
  "import cv2; print(hasattr(cv2, 'aruco'))"
```
Expect `True`.
```
docker run --rm --gpus all gs-reconstruction \
  conda run -n gs_preprocess python -c \
  "from transformers import AutoModelForImageSegmentation; \
   m = AutoModelForImageSegmentation.from_pretrained('ZhengPeng7/BiRefNet-DIS5K', trust_remote_code=True); \
   print('BiRefNet loaded OK')"
```
This needs internet access the first time (downloads model weights from
Hugging Face) and will be slow that one time. If it fails with an
`ImportError` naming some package, tell me the exact name and I'll add it
— that would mean the remote model code needs something beyond what I
could see in BiRefNet's published requirements.txt.

## 5. Running the actual pipeline

### Via the notebook (this is what changes least from before)
Inside the container:
```
conda activate gs_preprocess
jupyter lab --ip=0.0.0.0 --port=8888 --no-browser --allow-root
```
Copy the printed `http://127.0.0.1:8888/...` URL into your Windows
browser. Open `test_pipeline.ipynb`, and select the **"GS Reconstruction
(preprocess)"** kernel (Kernel → Change Kernel). From there, run the
notebook exactly as the README describes — same cells, same
`run_colmap(...)`, `run_filter_scene(...)`, `run_reconstruction(...)`,
`run_filter_plants(...)`, `run_scale_by_cameras(...)`, `run_meshing(...)`
calls. The two subprocess-based stages (`run_colmap`, `run_reconstruction`)
shell out to the bash scripts, which activate `gaussian_splatting_inria`
themselves — you never need to switch environments by hand for those.

One thing to check: `run_colmap`/`run_reconstruction` pass a
`colmap_script`/`reconstruction_script` path that the notebook builds from
`REPO_ROOT`. Inside the container that path is
`/workspace/GS_Reconstruction/...` rather than a Windows path — if the
notebook computes `REPO_ROOT` from its own file location (as the README's
example suggests), this should resolve correctly automatically since the
notebook itself now lives at that container path. If you see a "script
not found" error, print `colmap_script`/`reconstruction_script` in that
cell and check it against the container's actual layout.

### Direct bash execution (matches the README's own Section 6)
```
conda activate gaussian_splatting_inria
cd /workspace/GS_Reconstruction
bash src/run_colmap.sh --dataset Datasets/Reconstruction_test
bash src/run_reconstruction.sh \
    --dataset Datasets/Reconstruction_test \
    --output Outputs/Reconstruction_test_results/3d_reconstruction \
    --iterations 7000
```
Useful when a notebook error hides the real underlying failure — this
shows the full script output directly, matching the README's own advice.

## 6. Things worth knowing (found while reviewing the actual code)

- **Acquisition (`run_scan`) doesn't belong in this container.** Talking
  to the Jubilee machine stays on native Windows. Keep
  `hardware=False` inside the container and feed it a `Datasets/<name>/input/`
  folder that's already populated.
- **`3d_reconstruction_pipeline.py` will not run in this container.** It
  launches `start /wait cmd /k "wsl bash ..."` (Windows `cmd.exe` syntax)
  and imports the Jubilee hardware-control modules directly. It's the
  native-Windows orchestrator this container replaces the WSL leg of —
  not something to execute inside it.
- **`filter_plants.py`'s standalone CLI has a pre-existing bug**,
  unrelated to Docker: its `__main__` block passes `ban_hue_min`/
  `ban_hue_max` positionally into `filter_gaussians()`, which has no such
  parameters — everything after that shifts into the wrong slot. This
  only matters if you run `python filter_plants.py --input ... --output ...`
  directly; the notebook's `run_filter_plants` calls the function with
  keyword arguments and isn't affected.
- **`convert.py`'s `--resize` flag needs a `magick` binary that isn't in
  this image.** Not used by the pipeline's default invocation
  (`python convert.py -s <dataset_path>`, no `--resize`), so it's left
  out. If you ever need it: Ubuntu 22.04's `imagemagick` apt package is
  version 6 and doesn't provide `magick` at all, only `convert`/`mogrify`
  — ask if you need this and I'll add a working fix rather than a package
  that wouldn't actually solve it.
- **VRAM**: `--cap_max 2000000` (from the README's example) is a lot of
  Gaussians — how much VRAM that needs depends on scene complexity, and
  since this image is meant to run on more than one machine, I can't
  assume a specific GPU's VRAM budget here. If training runs out of
  memory on either machine, lower `--cap_max` first before suspecting
  anything else.
- **SIBR viewer** stays a native Windows binary outside Docker, pointed
  at the `Outputs/.../3d_reconstruction` folder this container produces.

## 7. If something fails during build

Docker build logs show the exact command that failed and its output —
scroll up to the last `RUN` line printed before the error. The most
likely spots, in order of how much they've historically bitten this
setup: the `pip install torch...` line (should show `cu118` wheels
downloading, not plain PyPI ones), and the two
`pip install submodules/...` lines (need submodules actually checked
out — `git submodule update --init --recursive` first).
