"""Tests for the Sacred GS Reconstruction launcher."""

from __future__ import annotations

import pytest

pytest.importorskip("sacred")

from science_jubilee.scripts import run_gs_reconstruction as reconstructor


@pytest.mark.vision
def test_reconstruction_launcher_delegates_to_pipeline(monkeypatch):
    """The launcher resolves Sacred config and delegates one pipeline call."""
    reconstructor.ex.observers.clear()

    calls = []

    def fake_run_pipeline(**kwargs):
        calls.append(kwargs)
        return {"mesh": "mesh.obj"}

    monkeypatch.setattr(reconstructor, "run_pipeline", fake_run_pipeline)

    result = reconstructor.ex.run(
        config_updates={
            "interactive": False,
            "hardware": False,
            "dataset_name": "Plante_1",
            "start": [110.0, 80.0, 280.0],
            "stop": [250.0, 200.0, 220.0],
            "steps": [5, 5, 4],
            "delay": 2.0,
            "iterations": 7000,
            "run_capture": False,
            "num_photos": 100,
            "show": True,
        }
    )

    assert result.status == "COMPLETED"
    assert result.result == {"mesh": "mesh.obj"}
    assert calls == [
        {
            "dataset_name": "Plante_1",
            "num_photos": 100,
            "iterations": 7000,
            "show": True,
            "run_capture": False,
            "start": [110.0, 80.0, 280.0],
            "stop": [250.0, 200.0, 220.0],
            "steps": [5, 5, 4],
            "delay": 2.0,
        }
    ]
