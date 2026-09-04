"""Mock-mode test for the monocular horizontal-leaves launcher."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

pytest.importorskip("sacred")

from science_jubilee.scripts import run_monocular_horizontals as launcher

logger = logging.getLogger(__name__)


@pytest.mark.vision
def test_monocular_horizontal_leaves_mock_run(monkeypatch, tmp_path):
    """Run the real mock session and image path through the Sacred launcher."""
    launcher.ex.observers.clear()

    repo_root = Path(__file__).resolve().parents[2]
    mock_image_path = (
        repo_root
        / "src"
        / "science_jubilee"
        / "Vision"
        / "Monocular_Horizontal_leaves"
        / "input"
        / "Mock_test.jpg"
    )

    pipeline_calls = []

    def fake_run_pipeline(**kwargs):
        pipeline_calls.append(kwargs)
        return {
            "targets": [
                {"xyz_mm": [float(index), 10.0, 20.0]}
                for index in range(6)
            ]
        }

    monkeypatch.setattr(launcher, "run_pipeline", fake_run_pipeline)

    result = launcher.ex.run(
        config_updates={
            "hardware": False,
            "session_env_mock": ".env.mock",
            "mock_image_path": str(mock_image_path),
            "output_dir": str(tmp_path),
            "image_settle": 0.0,
            "visit_count": 5,
            "supplementary_offset_xyz": [10.0, 20.0, 30.0],
        }
    )

    assert result.status == "COMPLETED"
    assert len(pipeline_calls) == 1
    assert pipeline_calls[0]["image"].shape[:2] == (1056, 1920)
    assert pipeline_calls[0]["image_name"] == "latest.jpg"
    assert pipeline_calls[0]["output_dir"] == str(tmp_path)
    assert result.result["targets"][-1]["xyz_mm"] == [5.0, 10.0, 20.0]
    assert (tmp_path / "latest.jpg").exists()
    logger.info("Mock monocular horizontal-leaves run completed successfully.")