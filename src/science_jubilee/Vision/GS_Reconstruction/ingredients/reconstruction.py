import os
from pathlib import Path
from sacred import Ingredient

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


@reconstruction.capture
def run_reconstruction(reconstruction_script, dataset_path, output_path, iterations=7000):
    script_wsl = _windows_to_wsl_path(reconstruction_script)
    dataset_wsl = _windows_to_wsl_path(str(Path(dataset_path).resolve()))
    output_wsl = _windows_to_wsl_path(str(Path(output_path).resolve()))
    cmd = f"start /wait cmd /k bash {script_wsl} --dataset {dataset_wsl} --output {output_wsl} --iterations {iterations}"
    res = os.system(cmd)
    if res != 0:
        raise RuntimeError(f"Reconstruction step failed with exit code {res}")
    return True
