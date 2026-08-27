import sys
from pathlib import Path

from sacred import Ingredient

_GS_ROOT = Path(__file__).resolve().parents[1]  # GS_Reconstruction/
if str(_GS_ROOT) not in sys.path:
    sys.path.insert(0, str(_GS_ROOT))

import src.filter_plants as filter_plants

post_process = Ingredient("post_process")


@post_process.config
def config():
    pass


@post_process.capture
def run_filter_plants(
    input_ply,
    output_ply,
    bbox_size,
    bbox_center,
    elongation_threshold,
    scale_threshold,
    std_ratio,
    opacity_threshold,
    nb_neighbors,
    white_sat_thresh,
    white_val_thresh,
):
    filter_plants.filter_gaussians(
        input_ply=str(input_ply),
        output_ply=str(output_ply),
        bbox_size=bbox_size,
        bbox_center=bbox_center,
        elongation_threshold=elongation_threshold,
        scale_threshold=scale_threshold,
        std_ratio=std_ratio,
        opacity_threshold=opacity_threshold,
        nb_neighbors=nb_neighbors,
        white_sat_thresh=white_sat_thresh,
        white_val_thresh=white_val_thresh,
    )
    return True
