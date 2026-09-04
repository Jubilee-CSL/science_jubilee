import json
from pathlib import Path

import cv2
import numpy as np
import yaml
from sacred import Ingredient

from science_jubilee.Vision.Monocular_Horizontal_leaves.ingredients.extract_leafs import run_leaf_clusters_to_opencv

from .inference_MoGe import (inference_MoGe,run_infer_depths_and_normals)
from .filter_scene import filter_scene, run_filter_scene
from .inference_marigold import (
	inference_marigold,
	run_infer_depths_and_normals,
)
from .depth_scaling import scale_depth, run_scale_depth
from .reconstruction import reconstruction, run_reconstruction as create_reconstruction
from .target_horizontals import (
	run_estimate_horizontal_targets,
	target_horizontals,
)
from .extract_leafs import ( extract_leafs, run_extract_leaf_clusters, run_leaf_clusters_to_opencv )

pipeline = Ingredient(
	"marigold_horizontal_leafs",
	ingredients=[filter_scene,extract_leafs,scale_depth, inference_marigold,inference_MoGe, reconstruction, target_horizontals],
)


@pipeline.config
def config():
	image_name = "latest.jpg"
	module_dir = Path(__file__).resolve().parents[1]
	output_dir = str(module_dir / "output" / Path(image_name).stem)
	steps = 50
	use_ai = True
	run_reconstruction = False
	model = "MoGe"
	tray_z_mm = 320.0
	plant_height = None
	scale_cube = None
	camera = None
	plant_hsv_lower = [70, 20, 25]
	plant_hsv_upper = [150, 100, 100]
	cube_hsv_lower = [170, 20, 39]
	cube_hsv_upper = [220, 100, 100]
	filtering_min_area_px = 500
	filtering_max_area_px = 150000
	cluster_eps_mm = 2.0
	cluster_eps_normal = 0.03
	normal_threshold = 0.90
	leaf_distance_threshold = 0.00113
	leaf_min_points = 20
	leaf_size_threshold = 1e-5
	leaf_shape_threshold = 0.98
	leaf_height_ratio = 0.01
	leaf_voxel_size = 0.0005
	reconstruction_alpha = 0.005
	reconstruction_decimate_ratio = 0.5
	reconstruction_output_dir = None


def _add_artifact(run, output_dir, filename, value, writer):
	output_path = Path(output_dir) / filename
	output_path.parent.mkdir(parents=True, exist_ok=True)
	writer(value, output_path)
	if run is not None:
		run.add_artifact(output_path, name=filename)


def _log_scalar(run, name, value):
	if run is not None and value is not None:
		run.log_scalar(name, float(value))


@pipeline.capture
def run_pipeline(
	image,
	image_name: str,
	output_dir,
	steps=None,
	run_reconstruction=True,
	model="MoGe",
	tray_z_mm=320.0,
	plant_height=None,
	scale_cube=None,
	camera=None,
	plant_hsv_lower=(70, 20, 25),
	plant_hsv_upper=(150, 100, 100),
	cube_hsv_lower=(170, 20, 39),
	cube_hsv_upper=(220, 100, 100),
	filtering_min_area_px=500,
	filtering_max_area_px=150000,
	cluster_eps_mm=2.0,
	cluster_eps_normal=0.03,
	normal_threshold=0.90,
	leaf_distance_threshold=0.00113,
	leaf_min_points=20,
	leaf_size_threshold=1e-5,
	leaf_shape_threshold=0.98,
	leaf_height_ratio=0.01,
	leaf_voxel_size=0.0005,
	reconstruction_alpha=0.005,
	reconstruction_decimate_ratio=0.5,
	reconstruction_output_dir=None,
	_run=None,
):
	
	image_bgr = np.asarray(image)
	output_dir = Path(output_dir)

	filtered = run_filter_scene(
		image=image,
		plant_hsv_lower=plant_hsv_lower,
		plant_hsv_upper=plant_hsv_upper,
		cube_hsv_lower=cube_hsv_lower,
		cube_hsv_upper=cube_hsv_upper,
	)
	tray_mask = np.asarray(filtered["tray_mask"])
	plant_mask = np.asarray(filtered["plant_mask"])
	cube_mask = np.asarray(filtered["cube_mask"])
	if model == "Marigold":
		from .inference_marigold import run_infer_depths_and_normals
		if plant_mask is None and scale_cube is None:
			raise ValueError("Marigold needs a reference object to scale onto the camera view")
		inference = inference_marigold(
			image=image,
			output_dir=str(output_dir),
			image_name=image_name,
			steps=steps,
		)

	elif model == "MoGe":
		from .inference_MoGe import run_infer_depths_and_normals

		inference = run_infer_depths_and_normals(
			image=image,
			output_dir=str(output_dir),
			image_name=image_name,
			resolution_level=10,
			refinement_steps=5,
			model_version=3,
		)
	else:
		raise ValueError(f"Unsupported model: {model}")
	depth_map = inference["depth"]
	normals = inference["normals"]
	
	depth_scaling_result = run_scale_depth(
		image=image,
		depth_map=depth_map,
		tray_mask=tray_mask,
		cube_mask=cube_mask,
		tray_z_mm=tray_z_mm,
		plant_height=plant_height,
		scale_cube=scale_cube,
    )
	depth_mm = depth_scaling_result["depth_mm"]
	tray_depth = depth_scaling_result["tray_depth"]
	cube_depth = depth_scaling_result["cube_depth"]
	reconstruction_result = create_reconstruction(
		image=image,
		depth_mm=depth_mm,
		camera=camera,
		meshing=False,
		alpha=0.005,
		decimate_ratio=0.5,
		output_dir=str(output_dir),
		image_name="pipeline_point_cloud.jpg",
	)
	point_cloud = reconstruction_result["point_cloud"]
	xyz_map=reconstruction_result["xyz_map"]
	leaf_clusters = run_extract_leaf_clusters(
		point_cloud,
		distance_threshold=leaf_distance_threshold,
		min_points=leaf_min_points,
		size_threshold=leaf_size_threshold,
		shape_threshold=leaf_shape_threshold,
		height_ratio=leaf_height_ratio,
		voxel_size=leaf_voxel_size,
	)

	leaf_mask_result = run_leaf_clusters_to_opencv(
		leaf_clusters=leaf_clusters,
		xyz_map=xyz_map,
		image_shape=image.shape,
	)
	leaf_labels_img = leaf_mask_result["labels_img"]
	leaf_masks = leaf_mask_result["masks"]
	leaf_contours = leaf_mask_result["contours"]

	targets_result = run_estimate_horizontal_targets(
		image=image,
		depth_mm=depth_mm,
		point_cloud=point_cloud,
		labels_img=leaf_labels_img,
		plant_mask=plant_mask,
		normals=normals,
		min_area_px=filtering_min_area_px,
		max_area_px=filtering_max_area_px,
		cluster_eps_mm=cluster_eps_mm,
		cluster_eps_normal=cluster_eps_normal,
		normal_threshold=normal_threshold,
		camera=camera,
	)
	targets = targets_result["targets"]
	target_labels_img = targets_result["labels_img"]
	target_normal_stds = targets_result["normal_stds"]
	mesh = None
	if run_reconstruction:
		reconstruction_dir = (
			Path(reconstruction_output_dir)
			if reconstruction_output_dir is not None
			else output_dir / "reconstruction"
		)
		results = create_reconstruction(
			image=image,
			depth_mm=depth_mm,
			camera=camera,
			meshing=True,
			alpha=reconstruction_alpha,
			decimate_ratio=reconstruction_decimate_ratio,
			output_dir=str(reconstruction_dir),
			image_name="test_plant.jpg"
		)

		# 4. Extraction du maillage
		mesh = results["mesh"]


	stem = Path(image_name).stem
	overlay = targets["overlay"]
	input_path = output_dir / f"{stem}_input.jpg"
	if input_path.exists() and _run is not None:
		_run.add_artifact(str(input_path), name=input_path.name)
	point_cloud_path = output_dir / f"{stem}_point_cloud.ply"
	if point_cloud_path.exists() and _run is not None:
		_run.add_artifact(point_cloud_path, name=point_cloud_path.name)
	if mesh is not None:
		mesh_path = Path(results["mesh_path"])
		if mesh_path.exists() and _run is not None:
			_run.add_artifact(mesh_path, name=mesh_path.name)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_image.jpg",
		image_bgr,
		lambda value, path: cv2.imwrite(str(path), value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_overlay.png",
		overlay,
		lambda value, path: cv2.imwrite(str(path), value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_depth.npy",
		depth_map,
		lambda value, path: np.save(path, value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_normals.npy",
		normals,
		lambda value, path: np.save(path, value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_tray_mask.png",
		filtered["tray_mask"],
		lambda value, path: cv2.imwrite(str(path), value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_plant_mask.png",
		filtered["plant_mask"],
		lambda value, path: cv2.imwrite(str(path), value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_depth_mm.npy",
		depth_mm,
		lambda value, path: np.save(path, value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_depth_preview.png",
		depth_scaling_result["depth_preview"],
		lambda value, path: cv2.imwrite(str(path), value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_leaf_labels.npy",
		leaf_labels_img,
		lambda value, path: np.save(path, value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_target_labels.npy",
		target_labels_img,
		lambda value, path: np.save(path, value),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_targets.json",
		targets["targets"],
		lambda value, path: path.write_text(
			json.dumps(value, indent=2), encoding="utf-8"
		),
	)
	debug_values = {
		"tray_depth_min": depth_scaling_result["tray_depth_min"],
		"tray_depth_max": depth_scaling_result["tray_depth_max"],
		"cube_depth_min": depth_scaling_result["cube_depth_min"],
		"cube_depth_max": depth_scaling_result["cube_depth_max"],
		"target_count": len(targets["targets"]),
		"leaf_count": len(leaf_clusters),
	}
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_debug.json",
		debug_values,
		lambda value, path: path.write_text(
			json.dumps(value, indent=2), encoding="utf-8"
		),
	)
	for name, value in debug_values.items():
		_log_scalar(_run, f"debug/{name}", value)

	result = {
		"image": image_bgr,
		"overlay": overlay,
		"depth": depth_map,
		"normals": normals,
		"point_cloud": point_cloud,
		"tray_mask": targets["tray_mask"],
		"plant_mask": targets["plant_mask"],
		"depth_mm": targets["depth_mm"],
		"targets": targets["targets"],
	}
	if mesh is not None:
		result["mesh"] = mesh
	return result
