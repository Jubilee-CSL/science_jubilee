from pathlib import Path
from sacred import Ingredient
import sys

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent

for p in (SRC_ROOT, REPO_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

import scale_by_cameras

scale_by_cameras_ing = Ingredient("scaling")


@scale_by_cameras_ing.config
def config():
    cameras_span = None


@scale_by_cameras_ing.capture
def run_scale_by_cameras(input_ply, output_ply, cameras_json_path, cameras_span):
    scale_by_cameras.main(
        input_ply=str(input_ply), output_ply=str(output_ply), cameras_json_path=cameras_json_path, cameras_span=cameras_span
    )
    return True
