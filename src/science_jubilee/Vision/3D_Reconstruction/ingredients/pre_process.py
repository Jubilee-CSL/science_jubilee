from pathlib import Path
from sacred import Ingredient

import sys

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent

for p in (SRC_ROOT, REPO_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

import src.filter_scene as filter_scene

pre_process= Ingredient("pre_process")


@pre_process.config
def config():
    use_ai= True


@pre_process.capture
def run_filter_scene(images_path):
    images_path = Path(images_path)
    filter_scene.main(images_path=images_path,use_ai=use_ai)
    return True
