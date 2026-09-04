import os
import sys
from pathlib import Path
import subprocess
from sacred import Ingredient

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent


colmap = Ingredient("colmap")


@colmap.config
def config():
    # path to the run_colmap.sh script (relative to repo)
    colmap_script = str(
        REPO_ROOT
        / "src/science_jubilee/Vision/GS_Reconstruction/src"
        / "run_colmap.sh"
    )
    run_dense=False


def _windows_to_wsl_path(windows_path: str) -> str:
    path = Path(windows_path).resolve()
    drive_letter = path.drive.rstrip(":").lower()
    return "/mnt/" + drive_letter + path.as_posix()[2:]


@colmap.capture
def run_colmap(colmap_script, dataset_path, run_dense):
    colmap_wsl = _windows_to_wsl_path(colmap_script)
    dataset_wsl = _windows_to_wsl_path(str(Path(dataset_path).resolve()))
    cmd = f"start /wait cmd /k bash {colmap_wsl} --dataset {dataset_wsl}"
    if run_dense:
        cmd += " --run_dense"
    # Run inside WSL; keep caller responsible for platform specifics
    res = os.system(cmd)
    if res != 0:
        raise RuntimeError(f"Colmap step failed with exit code {res}")
    return "Colmap succed"
