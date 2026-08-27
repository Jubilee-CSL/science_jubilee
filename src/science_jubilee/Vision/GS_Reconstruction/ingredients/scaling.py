import sys
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]  # GS_Reconstruction/
if str(_GS_ROOT) not in sys.path:
    sys.path.insert(0, str(_GS_ROOT))

import src.scale_by_cameras as scale_by_cameras

scaling = Ingredient("scaling")


@scaling.config
def config():
    pass


@scaling.capture
def run_scale_by_cameras(input_ply, output_ply, cameras_json_path, cameras_span):
    scale_by_cameras.main(
        input_ply=str(input_ply),
        output_ply=str(output_ply),
        cameras_json_path=cameras_json_path,
        cameras_span=cameras_span,
    )
    return True
