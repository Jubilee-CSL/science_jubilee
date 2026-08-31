import importlib.util
import subprocess
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]
_COMPOSE_FILE = str(_GS_ROOT / "docker-compose.yml")
_CONTAINER_ROOT = (
    "/workspace/science_jubilee/src/science_jubilee/Vision/GS_Reconstruction"
)
_FILTER_SCENE_PY = f"{_CONTAINER_ROOT}/src/filter_scene.py"
_FILTER_SCENE_SOURCE_PATH = _GS_ROOT / "src" / "filter_scene.py"

pre_process = Ingredient("pre_process")


@pre_process.config
def config():
    use_ai = False


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


def _to_container(host_path: Path, subdir: str) -> str:
    rel = host_path.resolve().relative_to((_GS_ROOT / subdir).resolve())
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


def _load_filter_scene():
    spec = importlib.util.spec_from_file_location(
        "gs_reconstruction_filter_scene", _FILTER_SCENE_SOURCE_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Unable to load scene filtering module: {_FILTER_SCENE_SOURCE_PATH}"
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pre_process.capture
def run_filter_scene(images_path, use_ai=False):
    if _is_docker_available():
        container_images = _to_container(Path(images_path), "Datasets")
        cmd = [
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
            "gs_preprocess",
            "python",
            _FILTER_SCENE_PY,
            "--images_path",
            container_images,
        ]
        if not use_ai:
            cmd.append("--no_ai")
        res = _stream(cmd)
        if res != 0:
            raise RuntimeError(f"filter_scene step failed (exit {res})")
    else:
        filter_scene = _load_filter_scene()
        filter_scene.main(images_path=Path(images_path), use_ai=use_ai)
    return True
