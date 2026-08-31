import subprocess
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]  # GS_Reconstruction/
_COMPOSE_FILE = str(_GS_ROOT / "docker-compose.yml")
_DATASETS_IN_COLMAP = "/datasets"  # mount point defined in docker-compose.yml

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent

colmap = Ingredient("colmap")


@colmap.config
def config():
    colmap_script = str(
        REPO_ROOT / "src/science_jubilee/Vision/GS_Reconstruction/src" / "run_colmap.sh"
    )


def _windows_to_wsl_path(windows_path: str) -> str:
    path = Path(windows_path).resolve()
    drive_letter = path.drive.rstrip(":").lower()
    return "/mnt/" + drive_letter + path.as_posix()[2:]


def _is_docker_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _host_to_colmap_path(host_path) -> str:
    scene = Path(host_path).resolve().relative_to((_GS_ROOT / "Datasets").resolve())
    return f"{_DATASETS_IN_COLMAP}/{scene.as_posix()}"


def _stream(cmd, label=""):
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    for line in proc.stdout:
        print(line, end="", flush=True)
    proc.wait()
    return proc.returncode


@colmap.capture
def run_colmap(
    dataset_path,
    colmap_script=str(
        REPO_ROOT / "src/science_jubilee/Vision/GS_Reconstruction/src" / "run_colmap.sh"
    ),
):
    if _is_docker_available():
        container_path = _host_to_colmap_path(dataset_path)
        res = _stream(
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
            "COLMAP",
        )
        if res != 0:
            raise RuntimeError(f"COLMAP step failed (exit {res})")

        sparse_dir = f"{container_path}/sparse/0"
        res = _stream(
            [
                "docker",
                "compose",
                "-f",
                _COMPOSE_FILE,
                "run",
                "--rm",
                "colmap",
                "colmap",
                "model_converter",
                "--input_path",
                sparse_dir,
                "--output_path",
                f"{sparse_dir}/points3D.ply",
                "--output_type",
                "PLY",
            ],
            "COLMAP PLY export",
        )
        if res != 0:
            raise RuntimeError(f"COLMAP PLY export failed (exit {res})")
    else:
        colmap_wsl = _windows_to_wsl_path(colmap_script)
        dataset_wsl = _windows_to_wsl_path(str(Path(dataset_path).resolve()))
        res = _stream(
            ["wsl", "bash", colmap_wsl, "--dataset", dataset_wsl],
            "COLMAP",
        )
        if res != 0:
            raise RuntimeError(f"COLMAP step failed (exit {res})")
    return "COLMAP succeeded"
