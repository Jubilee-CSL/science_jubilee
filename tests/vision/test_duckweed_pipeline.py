"""Mock-mode duckweed tracker pipeline smoke test.

This test imports the real `run_duckweed_tracker` script and executes the Sacred
experiment in mock mode with observers disabled.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from science_jubilee.scripts import run_duckweed_tracker as tracker

logger = logging.getLogger(__name__)


@pytest.mark.vision
def test_duckweed_pipeline_mock_run():
    # Disable Sacred observers (e.g., Mongo) for test/offline execution.
    tracker.ex.observers.clear()

    repo_root = Path(__file__).resolve().parents[2]
    mock_image_path = (
        repo_root
        / "src"
        / "science_jubilee"
        / "Vision"
        / "Duckweed_tracker"
        / "Filtered_images"
        / "test_duckweed_image.png"
    )

    result = tracker.ex.run(
        config_updates={
            "hardware": False,
            "use_ai": False,
            "session_env_mock": ".env.mock",
            "mock_image_path": str(mock_image_path),
            # Use single-well slot in mock to keep this test short.
            "source_slot": "0",
            "dest_slot": "1",
            "supplementary_offset_xyz": [-10.0, 10.0, 0.0],
            "image_settle": 0.0,
        }
    )

    assert result.status == "COMPLETED"
    logger.info("Mock duckweed tracker run completed successfully.")
