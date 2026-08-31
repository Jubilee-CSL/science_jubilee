"""Unit and smoke tests for the GS_Reconstruction ingredient pipeline.

All subprocess/Docker calls are mocked so the suite runs without Docker, WSL,
CUDA, or any PLY/dataset files on disk.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GS_ING = (
    Path(__file__).resolve().parents[2]
    / "src/science_jubilee/Vision/GS_Reconstruction/ingredients"
)


def _make_stream_mock(returncode: int = 0):
    """Return a _stream replacement that prints nothing and returns returncode."""
    return MagicMock(return_value=returncode)


# ---------------------------------------------------------------------------
# colmap ingredient
# ---------------------------------------------------------------------------


@pytest.mark.vision
class TestColmapIngredient:
    def setup_method(self):
        import sys

        # Reload to avoid Sacred config-state leakage between tests.
        mod_name = "science_jubilee.Vision.GS_Reconstruction.ingredients.colmap"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        import science_jubilee.Vision.GS_Reconstruction.ingredients.colmap as mod

        self.mod = mod

    def test_config_has_colmap_script(self):
        cfg = self.mod.colmap.configurations[0]()
        assert "colmap_script" in cfg
        assert cfg["colmap_script"].endswith("run_colmap.sh")

    def test_windows_to_wsl_path(self):
        result = self.mod._windows_to_wsl_path("C:\\Users\\test\\dataset")
        assert result.startswith("/mnt/c/")
        assert "Users/test/dataset" in result

    def test_is_docker_available_true(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            assert self.mod._is_docker_available() is True

    def test_is_docker_available_false_nonzero(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            assert self.mod._is_docker_available() is False

    def test_is_docker_available_false_not_found(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            assert self.mod._is_docker_available() is False

    def test_is_docker_available_false_timeout(self):
        with patch(
            "subprocess.run", side_effect=subprocess.TimeoutExpired("docker", 5)
        ):
            assert self.mod._is_docker_available() is False

    def test_run_colmap_uses_docker_when_available(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=True),
            patch.object(self.mod, "_stream", _make_stream_mock(0)) as mock_stream,
            patch.object(
                self.mod, "_host_to_colmap_path", return_value="/datasets/scene"
            ),
        ):
            result = self.mod.run_colmap(
                dataset_path="/fake/Datasets/scene",
                colmap_script="/fake/run_colmap.sh",
            )
        assert result == "COLMAP succeeded"
        first_call_cmd = mock_stream.call_args_list[0][0][0]
        assert "docker" in first_call_cmd

    def test_run_colmap_default_script_arg(self):
        # colmap_script must not be required when called outside Sacred
        with (
            patch.object(self.mod, "_is_docker_available", return_value=False),
            patch.object(self.mod, "_stream", _make_stream_mock(0)),
            patch.object(
                self.mod, "_windows_to_wsl_path", side_effect=lambda p: "/mnt/c/fake"
            ),
        ):
            result = self.mod.run_colmap(dataset_path="C:\\fake\\Datasets\\scene")
        assert result == "COLMAP succeeded"

    def test_run_colmap_falls_back_to_wsl(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=False),
            patch.object(self.mod, "_stream", _make_stream_mock(0)) as mock_stream,
            patch.object(
                self.mod, "_windows_to_wsl_path", side_effect=lambda p: "/mnt/c/fake"
            ),
        ):
            result = self.mod.run_colmap(
                dataset_path="C:\\fake\\Datasets\\scene",
                colmap_script="C:\\fake\\run_colmap.sh",
            )
        assert result == "COLMAP succeeded"
        cmd = mock_stream.call_args_list[0][0][0]
        assert cmd[0] == "wsl"
        assert "bash" in cmd

    def test_run_colmap_raises_on_docker_failure(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=True),
            patch.object(self.mod, "_stream", _make_stream_mock(1)),
            patch.object(
                self.mod, "_host_to_colmap_path", return_value="/datasets/scene"
            ),
        ):
            with pytest.raises(RuntimeError, match="COLMAP step failed"):
                self.mod.run_colmap(
                    dataset_path="/fake/Datasets/scene",
                    colmap_script="/fake/run_colmap.sh",
                )

    def test_run_colmap_raises_on_wsl_failure(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=False),
            patch.object(self.mod, "_stream", _make_stream_mock(1)),
            patch.object(
                self.mod, "_windows_to_wsl_path", side_effect=lambda p: "/mnt/c/fake"
            ),
        ):
            with pytest.raises(RuntimeError, match="COLMAP step failed"):
                self.mod.run_colmap(
                    dataset_path="C:\\fake\\Datasets\\scene",
                    colmap_script="C:\\fake\\run_colmap.sh",
                )


# ---------------------------------------------------------------------------
# reconstruction ingredient
# ---------------------------------------------------------------------------


@pytest.mark.vision
class TestReconstructionIngredient:
    def setup_method(self):
        import sys

        mod_name = "science_jubilee.Vision.GS_Reconstruction.ingredients.reconstruction"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        import science_jubilee.Vision.GS_Reconstruction.ingredients.reconstruction as mod

        self.mod = mod

    def test_config_has_reconstruction_script(self):
        cfg = self.mod.reconstruction.configurations[0]()
        assert "reconstruction_script" in cfg
        assert cfg["reconstruction_script"].endswith("run_reconstruction.sh")

    def test_run_reconstruction_uses_docker_when_available(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=True),
            patch.object(self.mod, "_stream", _make_stream_mock(0)) as mock_stream,
            patch.object(
                self.mod, "_to_container", side_effect=lambda p, s: f"/container/{s}"
            ),
        ):
            result = self.mod.run_reconstruction(
                dataset_path="/fake/Datasets/scene",
                output_path="/fake/Outputs/scene_results",
                reconstruction_script="/fake/run_reconstruction.sh",
                iterations=100,
            )
        assert result is True
        cmd = mock_stream.call_args_list[0][0][0]
        assert "docker" in cmd

    def test_run_reconstruction_default_script_arg(self):
        # reconstruction_script must not be required when called outside Sacred
        with (
            patch.object(self.mod, "_is_docker_available", return_value=False),
            patch.object(self.mod, "_stream", _make_stream_mock(0)),
            patch.object(
                self.mod, "_windows_to_wsl_path", side_effect=lambda p: "/mnt/c/fake"
            ),
        ):
            result = self.mod.run_reconstruction(
                dataset_path="C:\\fake\\Datasets\\scene",
                output_path="C:\\fake\\Outputs\\scene_results",
            )
        assert result is True

    def test_run_reconstruction_falls_back_to_wsl(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=False),
            patch.object(self.mod, "_stream", _make_stream_mock(0)) as mock_stream,
            patch.object(
                self.mod, "_windows_to_wsl_path", side_effect=lambda p: "/mnt/c/fake"
            ),
        ):
            result = self.mod.run_reconstruction(
                dataset_path="C:\\fake\\Datasets\\scene",
                output_path="C:\\fake\\Outputs\\scene_results",
                reconstruction_script="C:\\fake\\run_reconstruction.sh",
                iterations=100,
            )
        assert result is True
        cmd = mock_stream.call_args_list[0][0][0]
        assert cmd[0] == "wsl"
        assert "--iterations" in cmd
        assert "100" in cmd

    def test_run_reconstruction_raises_on_failure(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=False),
            patch.object(self.mod, "_stream", _make_stream_mock(1)),
            patch.object(
                self.mod, "_windows_to_wsl_path", side_effect=lambda p: "/mnt/c/fake"
            ),
        ):
            with pytest.raises(RuntimeError, match="Reconstruction step failed"):
                self.mod.run_reconstruction(
                    dataset_path="C:\\fake\\Datasets\\scene",
                    output_path="C:\\fake\\Outputs\\scene_results",
                    reconstruction_script="C:\\fake\\run_reconstruction.sh",
                )


# ---------------------------------------------------------------------------
# pre_process ingredient
# ---------------------------------------------------------------------------


@pytest.mark.vision
class TestPreProcessIngredient:
    def setup_method(self):
        import sys

        mod_name = "science_jubilee.Vision.GS_Reconstruction.ingredients.pre_process"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        import science_jubilee.Vision.GS_Reconstruction.ingredients.pre_process as mod

        self.mod = mod

    def test_config_use_ai_default(self):
        cfg = self.mod.pre_process.configurations[0]()
        assert cfg.get("use_ai") is False

    def test_run_filter_scene_uses_docker_when_available(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=True),
            patch.object(self.mod, "_stream", _make_stream_mock(0)) as mock_stream,
            patch.object(self.mod, "_to_container", return_value="/container/images"),
        ):
            result = self.mod.run_filter_scene(
                images_path="/fake/Datasets/scene/images", use_ai=True
            )
        assert result is True
        cmd = mock_stream.call_args_list[0][0][0]
        assert "docker" in cmd
        assert "--no_ai" not in cmd

    def test_run_filter_scene_docker_appends_no_ai_flag(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=True),
            patch.object(self.mod, "_stream", _make_stream_mock(0)) as mock_stream,
            patch.object(self.mod, "_to_container", return_value="/container/images"),
        ):
            self.mod.run_filter_scene(
                images_path="/fake/Datasets/scene/images", use_ai=False
            )
        cmd = mock_stream.call_args_list[0][0][0]
        assert "--no_ai" in cmd

    def test_run_filter_scene_falls_back_to_local(self):
        fake_module = MagicMock()
        with (
            patch.object(self.mod, "_is_docker_available", return_value=False),
            patch.object(self.mod, "_load_filter_scene", return_value=fake_module),
        ):
            result = self.mod.run_filter_scene(images_path="/fake/images", use_ai=False)
        assert result is True
        fake_module.main.assert_called_once_with(
            images_path=Path("/fake/images"), use_ai=False
        )

    def test_run_filter_scene_default_use_ai(self):
        # use_ai must not be required when called outside Sacred
        fake_module = MagicMock()
        with (
            patch.object(self.mod, "_is_docker_available", return_value=False),
            patch.object(self.mod, "_load_filter_scene", return_value=fake_module),
        ):
            result = self.mod.run_filter_scene(images_path="/fake/images")
        assert result is True
        fake_module.main.assert_called_once_with(
            images_path=Path("/fake/images"), use_ai=False
        )

    def test_run_filter_scene_raises_on_docker_failure(self):
        with (
            patch.object(self.mod, "_is_docker_available", return_value=True),
            patch.object(self.mod, "_stream", _make_stream_mock(1)),
            patch.object(self.mod, "_to_container", return_value="/container/images"),
        ):
            with pytest.raises(RuntimeError, match="filter_scene step failed"):
                self.mod.run_filter_scene(
                    images_path="/fake/Datasets/scene/images", use_ai=True
                )


# ---------------------------------------------------------------------------
# post_process ingredient (config defaults + basic import)
# ---------------------------------------------------------------------------


@pytest.mark.vision
class TestPostProcessIngredient:
    def setup_method(self):
        import sys

        mod_name = "science_jubilee.Vision.GS_Reconstruction.ingredients.post_process"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        import science_jubilee.Vision.GS_Reconstruction.ingredients.post_process as mod

        self.mod = mod

    def test_config_defaults(self):
        cfg = self.mod.post_process.configurations[0]()
        assert cfg["bbox_size"] == 10000
        assert cfg["bbox_center"] == [0.0, 2, 0.0]
        assert cfg["elongation_threshold"] == 7.0
        assert cfg["scale_threshold"] == 1
        assert cfg["std_ratio"] == 3
        assert cfg["opacity_threshold"] == 0.07
        assert cfg["nb_neighbors"] == 60
        assert cfg["white_sat_thresh"] == 0.55
        assert cfg["white_val_thresh"] == 0.2

    def test_run_filter_plants_missing_input_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            self.mod.run_filter_plants(
                input_ply=str(tmp_path / "nonexistent.ply"),
                output_ply=str(tmp_path / "out.ply"),
                bbox_size=10000,
                bbox_center=[0.0, 0.0, 0.0],
                elongation_threshold=7.0,
                scale_threshold=1,
                std_ratio=3,
                opacity_threshold=0.07,
                nb_neighbors=60,
                white_sat_thresh=0.55,
                white_val_thresh=0.2,
            )


# ---------------------------------------------------------------------------
# scaling ingredient (config defaults)
# ---------------------------------------------------------------------------


@pytest.mark.vision
class TestScalingIngredient:
    def setup_method(self):
        import sys

        mod_name = "science_jubilee.Vision.GS_Reconstruction.ingredients.scaling"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        import science_jubilee.Vision.GS_Reconstruction.ingredients.scaling as mod

        self.mod = mod

    def test_config_defaults(self):
        cfg = self.mod.scaling.configurations[0]()
        assert cfg["cameras_span"] is None


# ---------------------------------------------------------------------------
# meshing ingredient (config defaults)
# ---------------------------------------------------------------------------


@pytest.mark.vision
class TestMeshingIngredient:
    def setup_method(self):
        import sys

        mod_name = "science_jubilee.Vision.GS_Reconstruction.ingredients.meshing"
        if mod_name in sys.modules:
            del sys.modules[mod_name]
        import science_jubilee.Vision.GS_Reconstruction.ingredients.meshing as mod

        self.mod = mod

    def test_config_defaults(self):
        cfg = self.mod.meshing_ing.configurations[0]()
        assert cfg["alpha"] == pytest.approx(0.0038)
        assert cfg["decimate_ratio"] == pytest.approx(0.8)
