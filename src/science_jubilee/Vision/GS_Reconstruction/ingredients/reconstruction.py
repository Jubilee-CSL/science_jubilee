import subprocess
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]  # GS_Reconstruction/
_COMPOSE_FILE = str(_GS_ROOT / "docker-compose.yml")
_CONTAINER_ROOT = (
    "/workspace/science_jubilee/src/science_jubilee/Vision/GS_Reconstruction"
)
_TRAIN_PY = f"{_CONTAINER_ROOT}/src/3dgs-mcmc/train.py"

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent

reconstruction = Ingredient("reconstruction")


@reconstruction.config
def config():
    reconstruction_script = str(
        REPO_ROOT
        / "src/science_jubilee/Vision/GS_Reconstruction/src"
        / "run_reconstruction.sh"
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


def _to_container(host_path, subdir: str) -> str:
    rel = Path(host_path).resolve().relative_to((_GS_ROOT / subdir).resolve())
    return f"{_CONTAINER_ROOT}/{subdir}/{rel.as_posix()}"


def _stream(cmd):
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


@reconstruction.capture
def run_reconstruction(
    dataset_path,
    output_path,
    reconstruction_script=str(
        REPO_ROOT
        / "src/science_jubilee/Vision/GS_Reconstruction/src"
        / "run_reconstruction.sh"
    ),
    iterations=7000,
    cap_max=1_000_000,
):
    if _is_docker_available():
        ds = _to_container(dataset_path, "Datasets")
        out = _to_container(output_path, "Outputs")
        res = _stream(
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
                "--cap_max",
                str(cap_max),
            ],
        )
        if res != 0:
            raise RuntimeError(f"Reconstruction step failed (exit {res})")
    else:
        script_wsl = _windows_to_wsl_path(reconstruction_script)
        dataset_wsl = _windows_to_wsl_path(str(Path(dataset_path).resolve()))
        output_wsl = _windows_to_wsl_path(str(Path(output_path).resolve()))
        res = _stream(
            [
                "wsl",
                "bash",
                script_wsl,
                "--dataset",
                dataset_wsl,
                "--output",
                output_wsl,
                "--iterations",
                str(iterations),
            ],
        )
        if res != 0:
            raise RuntimeError(f"Reconstruction step failed (exit {res})")
    return True
