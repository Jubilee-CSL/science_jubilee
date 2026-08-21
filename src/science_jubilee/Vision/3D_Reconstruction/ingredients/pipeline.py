import logging
from pathlib import Path
import time
from sacred import Ingredient

from .colmap import colmap
from .reconstruction import reconstruction
from .filter_scene import filter_scene_ing
from .filter_plants import filter_plants_ing
from .scale_by_cameras import scale_by_cameras_ing
from .meshing import meshing_ing

logger = logging.getLogger(__name__)


pipeline = Ingredient(
    "3d_reconstruction_pipeline",
    ingredients=[colmap, filter_scene_ing, filter_plants_ing, scale_by_cameras_ing, meshing_ing, reconstruction],
)


@pipeline.config
def config():
    dataset_name = "Latest_reconstruction"
    num_photos = 100
    iterations = 7000
    show = True
    # filter_plants defaults are in its ingredient
    # meshing defaults are in its ingredient


@pipeline.capture
def run_pipeline(dataset_name, num_photos, iterations, show):
    REPO_ROOT = Path(__file__).resolve().parents[4].parent
    dataset_path = (
        REPO_ROOT / "src/science_jubilee/Vision/3D_Reconstruction/Datasets" / dataset_name
    )
    output_path = (
        REPO_ROOT / "src/science_jubilee/Vision/3D_Reconstruction/Outputs" / f"{dataset_name}_results"
    )
    images_dir = dataset_path / "input"
    output_path.mkdir(parents=True, exist_ok=True)

    debug_artifacts = {}
    run_tag = time.strftime("%Y%m%d_%H%M%S")

    logger.info("Starting 3D reconstruction pipeline for %s", dataset_name)

    # 1. Colmap conversion
    colmap.run_colmap(dataset_path=str(dataset_path))

    # 2. Filter scene (preprocessing)
    filter_scene_ing.run_filter_scene(images_path=str(dataset_path / "images"))

    # 3. Reconstruction (Gaussian training / reconstruction)
    reconstruction.run_reconstruction(
        dataset_path=str(dataset_path), output_path=str(output_path / "3d_reconstruction"), iterations=iterations
    )

    # 4. Filter plants (post-process point cloud)
    ply_path = output_path / "3d_reconstruction" / f"point_cloud/iteration_{iterations}" / "point_cloud.ply"
    filtered_ply = output_path / "3d_reconstruction" / "point_cloud/iteration_35000" / "point_cloud.ply"
    filtered_ply.parent.mkdir(parents=True, exist_ok=True)
    filter_plants_ing.run_filter_plants(
        input_ply=str(ply_path),
        output_ply=str(filtered_ply),
        bbox_size=10000,
        bbox_center=[0.0, 2, 0.0],
        elongation_threshold=7.0,
        scale_threshold=1,
        std_ratio=3,
        opacity_threshold=0.07,
        nb_neighbors=60,
        white_sat_thresh=0.55,
        white_val_thresh=0.2,
    )

    # 5. Scaling
    scaled_ply = output_path / "point_cloud_scaled.ply"
    cameras_json = output_path / "3d_reconstruction" / "cameras.json"
    scale_by_cameras_ing.run_scale_by_cameras(
        input_ply=str(filtered_ply), output_ply=str(scaled_ply), cameras_json_path=str(cameras_json), cameras_span=None
    )

    # 6. Meshing
    mesh_path = output_path / "mesh.obj"
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    meshing_ing.run_meshing(input_ply=str(scaled_ply), output_obj=str(mesh_path), alpha=0.0038, decimate_ratio=0.8)

    debug_artifacts["mesh"] = str(mesh_path)

    logger.info("Pipeline finished, mesh at %s", mesh_path)
    return {
        "mesh": str(mesh_path),
        "filtered_ply": str(filtered_ply),
        "scaled_ply": str(scaled_ply),
    }
