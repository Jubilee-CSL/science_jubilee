"""Tests for the snake_scan ingredient (motion + grid acquisition logic)."""

from pathlib import Path
from unittest.mock import patch

import pytest

from science_jubilee.scripts.ingredients.snake_scan import run_scan

_SESSION = "science_jubilee.scripts.ingredients.snake_scan.MachineSession"
_ACQUIRE = "science_jubilee.scripts.ingredients.snake_scan.acquire"


@pytest.fixture
def patched_session(session):
    """Inject the conftest mock session into run_scan's MachineSession.from_env."""
    with patch(_SESSION + ".from_env", return_value=session):
        yield session


def _fake_acquire(save_dir, name, **_):
    """Minimal acquire stub: creates the expected file and returns its path."""
    p = Path(save_dir) / f"{name}.jpg"
    p.touch()
    return str(p)


# ---------------------------------------------------------------------------
# Output folder
# ---------------------------------------------------------------------------


@pytest.mark.primary
def test_run_scan_creates_output_folder(patched_session, tmp_path):
    out = tmp_path / "grid"
    with patch(_ACQUIRE, side_effect=_fake_acquire):
        run_scan(start=[0.0, 0.0], stop=[10.0, 10.0], steps=[2, 2],
                 z=50.0, delay=0.0, out=str(out))
    assert out.is_dir()


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------


@pytest.mark.primary
def test_run_scan_returns_one_path_per_step(patched_session, tmp_path):
    with patch(_ACQUIRE, side_effect=_fake_acquire):
        saved = run_scan(start=[0.0, 0.0], stop=[20.0, 10.0], steps=[3, 4],
                         z=50.0, delay=0.0, out=str(tmp_path))
    assert len(saved) == 3 * 4


@pytest.mark.primary
def test_run_scan_returned_paths_exist(patched_session, tmp_path):
    with patch(_ACQUIRE, side_effect=_fake_acquire):
        saved = run_scan(start=[0.0, 0.0], stop=[10.0, 10.0], steps=[2, 3],
                         z=50.0, delay=0.0, out=str(tmp_path))
    assert all(Path(p).exists() for p in saved)


# ---------------------------------------------------------------------------
# Acquire call count
# ---------------------------------------------------------------------------


@pytest.mark.secondary
def test_run_scan_calls_acquire_for_every_position(patched_session, tmp_path):
    calls = []

    def counting_acquire(save_dir, name, **_):
        calls.append(name)
        p = Path(save_dir) / f"{name}.jpg"
        p.touch()
        return str(p)

    with patch(_ACQUIRE, side_effect=counting_acquire):
        run_scan(start=[0.0, 0.0], stop=[10.0, 10.0], steps=[3, 2],
                 z=50.0, delay=0.0, out=str(tmp_path))

    assert len(calls) == 3 * 2
    assert calls[0] == "snake_000_000"
    assert calls[1] == "snake_000_001"
    assert calls[2] == "snake_001_001"   # row 1 travels in reverse


@pytest.mark.secondary
def test_run_scan_1x1_grid_calls_acquire_once(patched_session, tmp_path):
    with patch(_ACQUIRE, side_effect=_fake_acquire) as mock_acq:
        run_scan(start=[5.0, 5.0], stop=[5.0, 5.0], steps=[1, 1],
                 z=50.0, delay=0.0, out=str(tmp_path))
    mock_acq.assert_called_once()
