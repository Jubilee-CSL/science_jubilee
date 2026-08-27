import sys
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]  # GS_Reconstruction/
if str(_GS_ROOT) not in sys.path:
    sys.path.insert(0, str(_GS_ROOT))

import src.filter_scene as filter_scene

pre_process = Ingredient("pre_process")


@pre_process.config
def config():
    pass


@pre_process.capture
def run_filter_scene(images_path, use_ai):
    images_path = Path(images_path)
    filter_scene.main(images_path=images_path, use_ai=use_ai)
    return True
