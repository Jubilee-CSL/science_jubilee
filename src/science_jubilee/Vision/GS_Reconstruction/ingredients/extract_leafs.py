from sacred import Ingredient

import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent

for path in (SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import src.extract_leafs as extract_leafs_src


extract_leafs = Ingredient("extract_leafs")


@extract_leafs.config
def config():
    distance_threshold = 0.01
    min_points = 50
    size_threshold = 0.005
    shape_threshold = 0.85
    height_ratio = 0.2


@extract_leafs.capture
def run_extract_leaf_clusters(
    pcd,
    distance_threshold,
    min_points,
    size_threshold,
    shape_threshold,
    height_ratio,
):
    return extract_leafs_src.extract_leaf_clusters(
        pcd=pcd,
        distance_threshold=distance_threshold,
        min_points=min_points,
        size_threshold=size_threshold,
        shape_threshold=shape_threshold,
        height_ratio=height_ratio,
    )


@extract_leafs.capture
def run_extract_normal_leafs(leaf_clusters, horizontal_threshold=0.8):
    return extract_leafs_src.extract_normal_leafs(
        leaf_clusters=leaf_clusters,
        horizontal_threshold=horizontal_threshold,
    )


@extract_leafs.capture
def run_compute_leaf_normals(leaf_clusters):
    return extract_leafs_src.compute_leaf_normals(leaf_clusters=leaf_clusters)