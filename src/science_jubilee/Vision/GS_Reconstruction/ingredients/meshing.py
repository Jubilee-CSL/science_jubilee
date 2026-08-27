import sys
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]  # GS_Reconstruction/
if str(_GS_ROOT) not in sys.path:
    sys.path.insert(0, str(_GS_ROOT))

import src.meshing as meshing

meshing_ing = Ingredient("meshing")


@meshing_ing.config
def config():
    pass


@meshing_ing.capture
def run_meshing(input_ply, output_obj, alpha, decimate_ratio):
    meshing.create_mesh_with_alpha_shape(
        input_ply=str(input_ply),
        output_obj=str(output_obj),
        alpha=alpha,
        decimate_ratio=decimate_ratio,
    )
    return True
