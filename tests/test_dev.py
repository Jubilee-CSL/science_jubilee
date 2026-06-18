import logging
import os

import torch

import pytest
from science_jubilee.tools.Observer import Camera

logger = logging.getLogger(__name__)


def test_cellpose():
    camera = Camera()

    # Check if CUDA is available
    logger.info(f"Is CUDA supported by this system? {torch.cuda.is_available()}")
    # Print CUDA version
    logger.info(f"CUDA version: {torch.version.cuda}")
    # Get current CUDA device ID
    cuda_id = torch.cuda.current_device()
    logger.info(f"ID of current CUDA device: {cuda_id}")
    # Get name of the current CUDA device
    logger.info(f"Name of current CUDA device: {torch.cuda.get_device_name(cuda_id)}")

    img_seg = camera.segment_latest_image()
    lentille_iso =camera.detect_isolated_duckweed(masks=img_seg,debug=True)
    print(lentille_iso)