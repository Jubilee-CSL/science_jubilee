import subprocess
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]  # GS_Reconstruction/
_COMPOSE_FILE = str(_GS_ROOT / "docker-compose.yml")
# Fixed paths inside the gs container (set by docker-compose.yml volumes)
_CONTAINER_ROOT = (
    "/workspace/science_jubilee/src/science_jubilee/Vision/GS_Reconstruction"
)
_TRAIN_PY = f"{_CONTAINER_ROOT}/src/3dgs-mcmc/train.py"

reconstruction = Ingredient("reconstruction")


@reconstruction.config
def config():
    pass


def _to_container(host_path, subdir: str) -> str:
    rel = Path(host_path).resolve().relative_to((_GS_ROOT / subdir).resolve())
    return f"{_CONTAINER_ROOT}/{subdir}/{rel.as_posix()}"


def run_reconstruction(dataset_path, output_path, iterations=7000):
    ds = _to_container(dataset_path, "Datasets")
    out = _to_container(output_path, "Outputs")
    res = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            _COMPOSE_FILE,
            "run",
            "--rm",
            "gs",
            "conda",
            "run",
            "--no-capture-output",
            "-n",
            "gaussian_splatting_inria",
            "python",
            _TRAIN_PY,
            "-s",
            ds,
            "-m",
            out,
            "--iterations",
            str(iterations),
        ],
        check=False,
    ).returncode
    if res != 0:
        raise RuntimeError(f"Reconstruction step failed (exit {res})")
    return True
