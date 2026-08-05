"""Tests for the acquisition ingredient (camera + lighting logic).

Run in mock (default) or against hardware:
    pytest tests/ingredients/ --jubilee-env mock
    pytest tests/ingredients/ --jubilee-env hardware --jubilee-address 192.168.1.2
"""

from unittest.mock import patch

import numpy as np
import pytest

from science_jubilee.scripts.ingredients.acquisition import (
    _capture_multi_lighting,
    _pixel_minimum,
    acquire,
)

_SLEEP = "science_jubilee.scripts.ingredients.acquisition.time.sleep"


# ---------------------------------------------------------------------------
# acquire() — simple mode
# ---------------------------------------------------------------------------


@pytest.mark.primary
def test_acquire_simple_returns_correct_path(camera, light, tmp_path):
    path = acquire(cam=camera, light=light, save_dir=tmp_path, name="img", mode="simple", nb_leds=8)
    assert path == str(tmp_path / "img.jpg")


@pytest.mark.primary
def test_acquire_simple_writes_file(camera, light, tmp_path):
    acquire(cam=camera, light=light, save_dir=tmp_path, name="img", mode="simple", nb_leds=8)
    assert (tmp_path / "img.jpg").exists()


@pytest.mark.primary
def test_acquire_simple_does_not_change_led_state(camera, light, tmp_path, jubilee_env):
    if jubilee_env == "mock":
        before = dict(light.state)
    acquire(cam=camera, light=light, save_dir=tmp_path, name="img", mode="simple", nb_leds=8)
    if jubilee_env == "mock":
        assert dict(light.state) == before


# ---------------------------------------------------------------------------
# acquire() — illuminated mode
# ---------------------------------------------------------------------------


@pytest.mark.invasive
def test_acquire_illuminated_returns_correct_path(camera, light, tmp_path):
    with patch(_SLEEP):
        path = acquire(cam=camera, light=light, save_dir=tmp_path, name="img", mode="illuminated", nb_leds=4)
    assert path == str(tmp_path / "img.jpg")


@pytest.mark.invasive
def test_acquire_illuminated_writes_file(camera, light, tmp_path):
    with patch(_SLEEP):
        acquire(cam=camera, light=light, save_dir=tmp_path, name="img", mode="illuminated", nb_leds=4)
    assert (tmp_path / "img.jpg").exists()


@pytest.mark.invasive
def test_acquire_illuminated_turns_leds_off_after(camera, light, tmp_path, jubilee_env):
    with patch(_SLEEP):
        acquire(cam=camera, light=light, save_dir=tmp_path, name="img", mode="illuminated", nb_leds=4)
    if jubilee_env == "mock":
        assert all(v == (0, 0, 0) for v in light.state.values())


@pytest.mark.primary
def test_acquire_illuminated_no_light_raises(camera, tmp_path):
    with pytest.raises(ValueError, match="light"):
        acquire(cam=camera, light=None, save_dir=tmp_path, name="img", mode="illuminated", nb_leds=8)


# ---------------------------------------------------------------------------
# _pixel_minimum  (pure — no session needed)
# ---------------------------------------------------------------------------


def test_pixel_minimum_takes_elementwise_min():
    a = np.array([[[100, 50, 200]]], dtype=np.uint8)
    b = np.array([[[ 80, 60, 150]]], dtype=np.uint8)
    c = np.array([[[120, 30, 180]]], dtype=np.uint8)
    result = _pixel_minimum([a, b, c])
    np.testing.assert_array_equal(result, np.array([[[80, 30, 150]]], dtype=np.uint8))


def test_pixel_minimum_does_not_modify_input():
    a = np.array([[[100]]], dtype=np.uint8)
    b = np.array([[[ 50]]], dtype=np.uint8)
    _pixel_minimum([a, b])
    np.testing.assert_array_equal(a, np.array([[[100]]], dtype=np.uint8))


# ---------------------------------------------------------------------------
# _capture_multi_lighting  (pure — no session needed)
# ---------------------------------------------------------------------------


@pytest.mark.primary
def test_capture_multi_lighting_returns_one_image_per_led(camera, light):
    with patch(_SLEEP):
        images = _capture_multi_lighting(camera, light, nb_leds=3)
    assert len(images) == 3


@pytest.mark.secondary
def test_capture_multi_lighting_turns_off_all_leds(camera, light, jubilee_env):
    with patch(_SLEEP):
        _capture_multi_lighting(camera, light, nb_leds=3)
    if jubilee_env == "mock":
        assert all(v == (0, 0, 0) for v in light.state.values())
