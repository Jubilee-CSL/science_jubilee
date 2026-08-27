import subprocess
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]  # GS_Reconstruction/
_COMPOSE_FILE = str(_GS_ROOT / "docker-compose.yml")
_DATASETS_IN_COLMAP = "/datasets"  # mount point defined in docker-compose.yml

colmap = Ingredient("colmap")


@colmap.config
def config():
    pass


def _host_to_colmap_path(host_path) -> str:
    scene = Path(host_path).resolve().relative_to((_GS_ROOT / "Datasets").resolve())
    return f"{_DATASETS_IN_COLMAP}/{scene.as_posix()}"


def run_colmap(dataset_path):
    container_path = _host_to_colmap_path(dataset_path)
    res = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            _COMPOSE_FILE,
            "run",
            "--rm",
            "colmap",
            "python3",
            "/convert.py",
            "-s",
            container_path,
        ],
        check=False,
    ).returncode
    if res != 0:
        raise RuntimeError(f"COLMAP step failed (exit {res})")
    return "COLMAP succeeded"
