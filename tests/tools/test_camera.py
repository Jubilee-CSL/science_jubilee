import logging
from types import SimpleNamespace

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
def test_autofocus_returns_bgr_array(camera):
    if hasattr(camera, "focus_mode"):
        camera.focus_mode("single")
    img = camera.autofocus()
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


@pytest.mark.secondary
def test_mock_camera_focus_api_matches_toolhead_camera():
    from science_jubilee.tools.camera.toolheadcam_mock import ToolheadCamMock

    camera = ToolheadCamMock(motion=None, tool_changer=None)

    assert camera.get_focus_mode() == "auto"
    with pytest.raises(RuntimeError, match="AfMode is 1"):
        camera.trigger_focus()

    camera.focus_mode("single")
    camera.trigger_focus(focus_seconds=3)

    assert camera.get_option("AfMode") == 1
    assert camera.get_option("AfTrigger") == 0


@pytest.mark.secondary
def test_mock_camera_configure_focus_normalizes_alias_and_sets_lens():
    from science_jubilee.tools.camera.toolheadcam_mock import ToolheadCamMock

    camera = ToolheadCamMock(motion=None, tool_changer=None)

    assert camera.configure_focus("autofocus") == "auto"
    assert camera.get_focus_mode() == "auto"

    assert camera.configure_focus("manual", lens_position=6) == "manual"
    assert camera.get_focus_mode() == "manual"
    assert camera.get_option("LensPosition") == 6


@pytest.mark.secondary
def test_mock_camera_trigger_single_autofocus_prepares_mode():
    from science_jubilee.tools.camera.toolheadcam_mock import ToolheadCamMock

    camera = ToolheadCamMock(motion=None, tool_changer=None)

    camera.trigger_single_autofocus(focus_seconds=3)

    assert camera.get_focus_mode() == "single"
    assert camera.get_option("AfTrigger") == 0


@pytest.mark.secondary
def test_mock_camera_status_and_forced_providers():
    from science_jubilee.tools.camera.toolheadcam_mock import ToolheadCamMock

    synthetic = np.full((10, 20, 3), 42, dtype=np.uint8)
    camera = ToolheadCamMock(
        motion=None,
        tool_changer=None,
        image_provider=lambda: synthetic,
    )

    status = camera.get_status()
    assert status["devices"][0]["options"]["afmode"]["value"] == "Continuous"
    np.testing.assert_array_equal(camera.get_image(), synthetic)

    camera.set_mock_option("AfMode", 1)
    assert camera.get_status()["devices"][0]["options"]["afmode"]["value"] == "Auto"


@pytest.mark.secondary
def test_toolhead_trigger_focus_requires_single_focus_mode():
    from science_jubilee.tools.camera.toolheadcam import ToolheadCam

    camera = ToolheadCam.__new__(ToolheadCam)
    camera.get_option = lambda key: 2

    with pytest.raises(RuntimeError, match="AfMode is 1"):
        camera.trigger_focus()


@pytest.mark.secondary
def test_toolhead_trigger_focus_does_not_change_focus_mode(monkeypatch):
    from science_jubilee.tools.camera import toolheadcam
    from science_jubilee.tools.camera.toolheadcam import ToolheadCam

    camera = ToolheadCam.__new__(ToolheadCam)
    calls = []

    def fake_keep_alive(seconds):
        calls.append(("keep_alive", seconds))

    def fake_set_option(key, value):
        calls.append((key, value))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(camera, "get_option", lambda key: 1)
    monkeypatch.setattr(camera, "keep_alive", fake_keep_alive)
    monkeypatch.setattr(camera, "set_option", fake_set_option)
    monkeypatch.setattr(toolheadcam.time, "sleep", lambda seconds: None)

    camera.trigger_focus(focus_seconds=3)

    assert ("keep_alive", 3) in calls
    assert ("AfTrigger", 0) in calls
    assert ("AfMode", 1) not in calls


@pytest.mark.secondary
def test_toolhead_trigger_single_autofocus_sets_mode_before_trigger(monkeypatch):
    from science_jubilee.tools.camera import toolheadcam
    from science_jubilee.tools.camera.toolheadcam import ToolheadCam

    camera = ToolheadCam.__new__(ToolheadCam)
    calls = []

    def fake_keep_alive(seconds):
        calls.append(("keep_alive", seconds))

    def fake_set_option(key, value):
        calls.append((key, value))
        return SimpleNamespace(status_code=200)

    monkeypatch.setattr(camera, "keep_alive", fake_keep_alive)
    monkeypatch.setattr(camera, "set_option", fake_set_option)
    monkeypatch.setattr(toolheadcam.time, "sleep", lambda seconds: None)

    camera.trigger_single_autofocus(focus_seconds=4)

    assert ("AfMode", 1) in calls
    assert ("keep_alive", 4) in calls
    assert ("AfTrigger", 0) in calls


@pytest.mark.secondary
def test_toolhead_get_focus_mode_queries_camera(monkeypatch):
    from science_jubilee.tools.camera.toolheadcam import ToolheadCam

    camera = ToolheadCam.__new__(ToolheadCam)
    monkeypatch.setattr(camera, "get_option", lambda key: 1)

    assert camera.get_focus_mode() == "single"


@pytest.mark.secondary
def test_toolhead_get_option_reads_webcam_status(monkeypatch):
    from science_jubilee.tools.camera.toolheadcam import ToolheadCam

    camera = ToolheadCam.__new__(ToolheadCam)
    monkeypatch.setattr(
        camera,
        "get_status",
        lambda: {
            "devices": [
                {
                    "name": "CAMERA",
                    "options": {
                        "afmode": {
                            "menu": {"0": "Manual", "1": "Auto", "2": "Continuous"},
                            "name": "AfMode",
                            "type": "integer",
                            "value": "Continuous",
                        },
                        "lensposition": {
                            "name": "LensPosition",
                            "type": "float",
                            "value": "12.000000",
                        },
                    },
                }
            ]
        },
    )

    assert camera.get_option("AfMode") == 2
    assert camera.get_option("LensPosition") == 12.0


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

    saved = sorted(tmp_path.glob("*.jpg"))
    assert len(saved) == 2
