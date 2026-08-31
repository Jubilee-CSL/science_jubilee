# ──────────────────────────────────────────────────────────────────────────────
# GS Reconstruction — lean Dockerfile
#
# Why this base: nvidia/cuda:11.7.1-devel gives us nvcc + CUDA headers at
# /usr/local/cuda — no separate conda CUDA package needed. The old approach
# (colmap/colmap runtime base + conda-forge cudatoolkit-dev on top) produced
# two redundant CUDA stacks and a ~50 GB image.
#
# COLMAP: installed via conda inside the training env, same approach as
#   https://github.com/ookami125/gaussian-splatting-docker
#
# Two conda envs (names and scripts unchanged):
#   gaussian_splatting_inria (python=3.8) — COLMAP, 3dgs-mcmc, CUDA extensions
#   gs_preprocess            (python=3.10) — BiRefNet, open3d, notebook kernel
#
# Build (from repo root):
#   docker build -t gs-reconstruction \
#     -f src/science_jubilee/Vision/GS_Reconstruction/Dockerfile .
#
# Target a single GPU arch for a faster build, e.g. RTX 30-series:
#   docker build --build-arg TORCH_CUDA_ARCH_LIST="8.6" -t gs-reconstruction ...
# ──────────────────────────────────────────────────────────────────────────────
FROM nvidia/cuda:11.7.1-devel-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TRAIN_ENV=gaussian_splatting_inria
ENV PREP_ENV=gs_preprocess
# nvcc + headers already at /usr/local/cuda in the devel image
ENV CUDA_HOME=/usr/local/cuda

# ── System packages ───────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential git wget ninja-build ffmpeg \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# ── Miniconda ─────────────────────────────────────────────────────────────────
RUN wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh \
        -O /tmp/miniconda.sh \
    && bash /tmp/miniconda.sh -b -p /opt/conda \
    && rm /tmp/miniconda.sh
ENV PATH=/opt/conda/bin:${PATH}

# Required since conda 24.9
RUN conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main \
    && conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r

# libmamba solver is substantially faster than the default classic solver
RUN conda install -n base -y conda-libmamba-solver \
    && conda config --set solver libmamba

# ── ENV 1: gaussian_splatting_inria ───────────────────────────────────────────
# python=3.8 matches the 3dgs-mcmc README and environment.yml
RUN conda create -y -n ${TRAIN_ENV} -c conda-forge python=3.8 \
    && conda clean --all -y

RUN conda run -n ${TRAIN_ENV} pip install \
    plyfile tqdm ninja \
    torch==1.13.1+cu117 torchvision==0.14.1+cu117 torchaudio==0.13.1 \
    --extra-index-url https://download.pytorch.org/whl/cu117 \
    && conda run -n ${TRAIN_ENV} pip cache purge

# ── Repo copy ─────────────────────────────────────────────────────────────────
COPY . /workspace/science_jubilee
ENV GS_ROOT=/workspace/science_jubilee/src/science_jubilee/Vision/GS_Reconstruction
ENV PYTHONPATH=/workspace/science_jubilee/src

RUN sed -i 's#^source .*conda\.sh#source /opt/conda/etc/profile.d/conda.sh#' \
    ${GS_ROOT}/src/run_colmap.sh \
    ${GS_ROOT}/src/run_reconstruction.sh

# ── Build CUDA extensions ─────────────────────────────────────────────────────
WORKDIR ${GS_ROOT}/src/3dgs-mcmc

# torch 1.13.1 supports up to arch 8.6 — 8.9 (Ada Lovelace) raises ValueError
ARG TORCH_CUDA_ARCH_LIST="6.1;7.0;7.5;8.0;8.6+PTX"
ENV TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST}

RUN conda run -n ${TRAIN_ENV} pip install \
    submodules/diff-gaussian-rasterization \
    submodules/simple-knn \
    && conda run -n ${TRAIN_ENV} pip cache purge

# ── ENV 2: gs_preprocess ──────────────────────────────────────────────────────
WORKDIR ${GS_ROOT}

RUN conda create -y -n ${PREP_ENV} -c conda-forge python=3.10 \
    && conda clean --all -y

RUN conda run -n ${PREP_ENV} pip install \
    torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 \
    --index-url https://download.pytorch.org/whl/cu118 \
    && conda run -n ${PREP_ENV} pip cache purge

# ultralytics can silently downgrade opencv-contrib; install last and force it back
RUN conda run -n ${PREP_ENV} pip install \
    "numpy<2" timm scipy scikit-image kornia einops tqdm \
    prettytable tabulate "huggingface-hub>0.25" accelerate \
    ultralytics transformers pillow \
    sacred matplotlib open3d plyfile \
    && conda run -n ${PREP_ENV} pip install --force-reinstall --no-deps \
        opencv-contrib-python-headless \
    && conda run -n ${PREP_ENV} pip cache purge

RUN echo "conda activate ${PREP_ENV}" >> /root/.bashrc

# ── Runtime ───────────────────────────────────────────────────────────────────
CMD ["bash"]
