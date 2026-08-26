import logging
from pathlib import Path
import os
import open3d as o3d
from sacred import Ingredient

from science_jubilee.scripts.ingredients.snake_scan import run_scan, scan

from .colmap import run_colmap, colmap
from .extract_leafs import run_extract_normal_leafs,run_extract_leaf_clusters, extract_leafs
from .meshing import run_meshing,    meshing_ing
from .post_process import run_filter_plants,post_process
from .pre_process import run_filter_scene, pre_process
from .reconstruction import run_reconstruction, reconstruction
from .scaling import run_scale_by_cameras, scaling

logger = logging.getLogger(__name__)


pipeline = Ingredient(
    "3d_reconstruction_pipeline",
    ingredients=[
        scan,
        colmap,
        pre_process,
        post_process,
        scaling,
        meshing_ing,
        reconstruction,
        extract_leafs,
    ],
)


@pipeline.config
def config():
    dataset_name = "Latest_reconstruction"
    num_photos = 100
    iterations = 7000
    show = True
    run_capture = True
    start = [110.0, 80.0, 280.0]
    stop = [250.0, 200.0, 220.0]
    steps = [5, 5, 4]
    delay = 2.0


@pipeline.capture
def run_pipeline(
    dataset_name,
    num_photos,
    iterations,
    show,
    run_capture,
    start,
    stop,
    steps,
    delay,
):
    repo_root = Path(__file__).resolve().parents[4].parent
    dataset_path = (
        repo_root
        / "src/science_jubilee/Vision/GS_Reconstruction/Datasets"
        / dataset_name
    )
    output_path = (
        repo_root
        / "src/science_jubilee/Vision/GS_Reconstruction/Outputs"
        / f"{dataset_name}_results"
    )
    images_dir = dataset_path / "input"
    dataset_path.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info("Starting 3D reconstruction pipeline for %s", dataset_name)

    if run_capture:
        saved_images = run_scan(
            start=start,
            stop=stop,
            steps=steps,
            delay=delay,
            out=str(images_dir),
        )

    else:
        saved_images = sorted(str(path) for path in images_dir.glob("*.jpg"))
        if not saved_images:
            raise FileNotFoundError(f"No input images found in {images_dir}")

    run_colmap(dataset_path=str(dataset_path))
    run_filter_scene(
        images_path=str(dataset_path / "images"),
        use_ai=True,
    )

    reconstruction_path = output_path / "3d_reconstruction"
    run_reconstruction(
        dataset_path=str(dataset_path),
        output_path=str(reconstruction_path),
        iterations=iterations,
    )

    reconstruction_ply = (
        reconstruction_path
        / "point_cloud"
        / f"iteration_{iterations}"
        / "point_cloud.ply"
    )
    filtered_ply = (
        reconstruction_path
        / "point_cloud"
        / "iteration_35000"
        / "point_cloud.ply"
    )
    filtered_ply.parent.mkdir(parents=True, exist_ok=True)
    run_filter_plants(
        input_ply=str(reconstruction_ply),
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

    scaled_ply = (
        reconstruction_path
        / "point_cloud"
        / "iteration_35000"
        / "point_cloud_scaled.ply"
    )
    scaled_ply.parent.mkdir(parents=True, exist_ok=True)
    run_scale_by_cameras(
        input_ply=str(filtered_ply),
        output_ply=str(scaled_ply),
        cameras_json_path=str(reconstruction_path / "cameras.json"),
        cameras_span=None,
        rot=[3.2, 0.8, 0.0],
    )

    mesh_path = output_path / "mesh.obj"
    run_meshing(
        input_ply=str(scaled_ply),
        output_obj=str(mesh_path),
        alpha=0.0038,
        decimate_ratio=0.8,
    )


    mesh = o3d.io.read_triangle_mesh(str(mesh_path))
    if not mesh.has_vertices():
        raise ValueError(f"Mesh has no vertices: {mesh_path}")
    mesh_pcd = o3d.geometry.PointCloud(mesh.vertices)
    leaf_clusters = run_extract_leaf_clusters(
        pcd=mesh_pcd,
        distance_threshold=0.0092,
        min_points=20,
        size_threshold=1e-5,
        shape_threshold=0.98,
        height_ratio=0.1,
    )
    horizontal_leaf_clusters = run_extract_normal_leafs(
        leaf_clusters=leaf_clusters,
        horizontal_threshold=0.90,
    )

    horizontal_leafs_ply = output_path / "horizontal_leafs.ply"
    horizontal_pcd = o3d.geometry.PointCloud()
    if horizontal_leaf_clusters:
        horizontal_points = [
            point for leaf in horizontal_leaf_clusters for point in leaf.points
        ]
        horizontal_pcd.points = o3d.utility.Vector3dVector(horizontal_points)
    o3d.io.write_point_cloud(str(horizontal_leafs_ply), horizontal_pcd)

    if show:
        Viewer_path = (
            repo_root / "src/science_jubilee/Vision/3D_Reconstruction/Viewer/bin"
        )
        # Gaussian Viewer
        os.system(
            f"cd {Viewer_path} && SIBR_gaussianViewer_app.exe -m {reconstruction_path }"
        )
        # Display the mesh
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        o3d.visualization.draw_geometries([mesh], mesh_show_back_face=True)

    logger.info(
        "Pipeline finished: %d leaves, %d horizontal leaves, mesh at %s",
        len(leaf_clusters),
        len(horizontal_leaf_clusters),
        mesh_path,
    )
    return {
        "dataset": str(dataset_path),
        "images": saved_images,
        "reconstruction_ply": str(reconstruction_ply),
        "filtered_ply": str(filtered_ply),
        "scaled_ply": str(scaled_ply),
        "mesh": str(mesh_path),
        "horizontal_leafs_ply": str(horizontal_leafs_ply),
        "leaf_count": len(leaf_clusters)-1,
        "horizontal_leaf_count": len(horizontal_leaf_clusters),
    }
