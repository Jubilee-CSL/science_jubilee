# GS_Reconstruction — Docker setup

This container **replaces WSL only**. Nothing about the pipeline itself
changes: same `gaussian_splatting_inria` conda env name, same
`run_colmap.sh` / `run_reconstruction.sh`, same `test_pipeline.ipynb`,
same Sacred ingredients. If you were previously running everything
through WSL, you now run it through this container instead — the
commands you type inside it are the same ones the README already
described.

The only actual code change is one line: `run_colmap.sh` and
`run_reconstruction.sh` hardcode `source C:/Users/Alienor/anaconda3/...`
to find conda, which only made sense inside WSL talking to a Windows
install. The Dockerfile patches that one line to point at conda's
location inside the container. Everything else is untouched.

## Why there are two conda environments inside one container

`filter_scene.py`'s AI segmentation step loads a BiRefNet model via
`transformers`. BiRefNet's own `requirements.txt` requires `torch>=2.5.0`.
PyTorch stopped publishing Python 3.8 wheels at torch 2.5. But Python 3.8
is what the `colmap` / `gxx_linux-64` combo in the README needs. Those two
requirements can't both be satisfied in one environment — not because of
Docker, but because of that one version fact. So:

- `gaussian_splatting_inria` (Python 3.8) — COLMAP, the compiled CUDA
  extensions, `train.py`. Exactly as the README's section 2.2 describes.
- `gs_preprocess` (Python 3.10) — everything else: the notebook kernel,
  `filter_scene.py`, `filter_plants.py`, `scale_by_cameras.py`, `meshing.py`.

You'll mostly work inside `gs_preprocess` (it's what Jupyter uses by
default). `gaussian_splatting_inria` gets activated automatically by the
bash scripts when they run COLMAP/training — you don't need to think
about it unless you're debugging that stage directly.

## Where this harvests an existing image instead of building from scratch

The base image is `colmap/colmap:latest` — the COLMAP project's own
official image — rather than a bare `nvidia/cuda` image with `colmap`
installed via conda. Their build compiles COLMAP for
`CUDA_ARCHITECTURES=all-major`, so the COLMAP binary itself is already
portable across GPUs, and it skips conda-forge's colmap resolution
(Boost, Ceres-Solver, Qt, CGAL — a slow, occasionally fragile solve) in
favor of a binary that's already compiled and tested upstream.

The trade-off: their current image is built on Ubuntu 24.04, not 22.04.
I haven't been able to build-test this myself (no Docker or network
access in my own tool environment — see below), so if the build behaves
unexpectedly, an Ubuntu-version-related apt package mismatch is the
first thing to suspect. Our own CUDA toolkit for the extensions is
self-contained via conda regardless (installed separately, matching the
README's own approach), so it doesn't depend on anything the base image
provides beyond a working `colmap` binary and normal apt access.

## 1. One-time host setup

- Docker Desktop → Settings → General → "Use the WSL 2 based engine"
- Docker Desktop → Settings → Resources → WSL Integration → enable your distro
- Confirm GPU passthrough works:
  ```
  docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
  ```
  You should see whatever GPU is in that machine listed, not an error.

## 2. Build the image

Build context must be the `GS_Reconstruction` folder itself (containing
`src/`, `ingredients/`, `test_pipeline.ipynb`), with submodules checked out:
```
cd GS_Reconstruction
git submodule update --init --recursive
```
Put the `Dockerfile` in that folder, then:
```
docker build -t gs-reconstruction .
```
Expect 20–40 minutes the first time — COLMAP, the CUDA toolkit, two CUDA
extension builds, and the ML packages all get built/installed.

## 3. Run the container

```
docker run --rm -it --gpus all ^
  -v "%cd%\Datasets:/workspace/GS_Reconstruction/Datasets" ^
  -v "%cd%\Outputs:/workspace/GS_Reconstruction/Outputs" ^
  -p 8888:8888 ^
  gs-reconstruction
```
(`^` is cmd's line-continuation character; drop it and put everything on
one line if you're using PowerShell.)

Your `Datasets/` and `Outputs/` folders are the only things that cross
the container boundary — everything you produce lands back on your disk
exactly where you'd expect, same as it did through WSL.

## 4. Test before running anything real

These catch the two things most likely to go wrong, before you spend
20 minutes on an actual reconstruction only to have it fail at the end.

**Training env — torch sees the GPU, and the compiled extensions load:**
```
docker run --rm --gpus all gs-reconstruction \
  conda run -n gaussian_splatting_inria python -c \
  "import torch; print(torch.__version__, torch.version.cuda, torch.cuda.is_available())"
```
Expect `2.0.1 11.8 True`.
```
docker run --rm --gpus all gs-reconstruction \
  conda run -n gaussian_splatting_inria python -c \
  "from diff_gaussian_rasterization import _C; print('extension OK')"
```
If this raises `no kernel image is available for execution on the
device`, the build's `TORCH_CUDA_ARCH_LIST` doesn't cover whatever GPU
is actually in the machine running the container. The Dockerfile default
covers Pascal through Ada (GTX 10-series through RTX 40-series) plus a
PTX fallback for anything newer — broad on purpose, since this image
isn't necessarily built and run on the same machine. If you know the
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
