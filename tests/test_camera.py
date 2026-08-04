import logging
from pathlib import Path

import numpy as np
import pytest

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Secondary: image acquisition, no motion
# ------------------------------------------------------------------

@pytest.mark.secondary
def test_get_image_returns_bgr_array(camera):
    img = camera.get_image()
    assert isinstance(img, np.ndarray)
    assert img.ndim == 3
    assert img.shape[2] == 3
    assert img.dtype == np.uint8


@pytest.mark.secondary
def test_save_image_writes_file(camera, tmp_path):
    img = camera.get_image()
    camera.save_image(img=img, save_dir=tmp_path, save_name="snap")
    files = list(tmp_path.glob("*.jpg"))
    assert len(files) == 1
    logger.info("Saved to %s", files[0])


@pytest.mark.secondary
def test_mock_camera_injected_image(camera):
    """MockCamera returns the injected image exactly (skipped on hardware)."""
    from science_jubilee.tools.camera.toolheadcam_mock import ToolheadCamMock
    if not isinstance(camera, ToolheadCamMock):
        pytest.skip("injected-image test is mock-only")
    synthetic = np.full((480, 640, 3), 128, dtype=np.uint8)
    camera._image = synthetic
    result = camera.get_image()
    np.testing.assert_array_equal(result, synthetic)
    camera._image = None


# ------------------------------------------------------------------
# Invasive: motion + acquisition at two positions
# ------------------------------------------------------------------

@pytest.mark.invasive
def test_acquire_image_at_two_positions(camera, tmp_path):
    """Move to two XY positions, capture and save one image at each."""
    positions = [
        (100.0, 100.0, 50.0),
        (150.0, 150.0, 50.0),
    ]
    for idx, (x, y, z) in enumerate(positions):
        camera.move_to_get_image(x, y, z)
        img = camera.get_image()
        assert img.ndim == 3
        camera.save_image(img=img, save_dir=tmp_path, save_name=f"pos_{idx}")
        logger.info("Position %d: T_camera=%s", idx, camera.T_machine_camera)

    saved = sorted(tmp_path.glob("*.jpg"))
    assert len(saved) == 2



# ------------------------------------------------------------------
# Hardware camera (skipped in mock mode)
# ------------------------------------------------------------------


@pytest.mark.invasive
def test_hardware_camera_get_image(camera):
    img = camera.get_image()
    assert isinstance(img, np.ndarray)
    assert img.ndim == 3
    logger.info("Captured image shape: %s", img.shape)
