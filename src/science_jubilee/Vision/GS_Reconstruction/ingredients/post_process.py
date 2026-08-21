from pathlib import Path
from sacred import Ingredient
import sys

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent

for p in (SRC_ROOT, REPO_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

import src.filter_plants as filter_plants

post_process = Ingredient("post_process")


@post_process.config
def config():
    bbox_size = 10000
    bbox_center = [0.0, 2, 0.0]
    elongation_threshold = 7.0
    scale_threshold = 1
    std_ratio = 3
    opacity_threshold = 0.07
    nb_neighbors = 60
    white_sat_thresh = 0.55
    white_val_thresh = 0.2


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
