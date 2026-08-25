from pathlib import Path
import importlib.util
from sacred import Ingredient

import sys

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent

for p in (SRC_ROOT, REPO_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

FILTER_SCENE_SOURCE_PATH = Path(__file__).resolve().parents[1] / "src" / "filter_scene.py"
FILTER_SCENE_SOURCE_SPEC = importlib.util.spec_from_file_location(
    "gs_reconstruction_filter_scene", FILTER_SCENE_SOURCE_PATH
)
if FILTER_SCENE_SOURCE_SPEC is None or FILTER_SCENE_SOURCE_SPEC.loader is None:
    raise ImportError(f"Unable to load scene filtering module: {FILTER_SCENE_SOURCE_PATH}")
filter_scene = importlib.util.module_from_spec(FILTER_SCENE_SOURCE_SPEC)
FILTER_SCENE_SOURCE_SPEC.loader.exec_module(filter_scene)

pre_process = Ingredient("pre_process")


@pre_process.config
def config():
    use_ai = True


@pre_process.capture
def run_filter_scene(images_path, use_ai):
    images_path = Path(images_path)
    filter_scene.main(images_path=images_path, use_ai=use_ai)
    return True
