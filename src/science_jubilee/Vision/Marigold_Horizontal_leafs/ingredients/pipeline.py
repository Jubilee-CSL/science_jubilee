import json
from pathlib import Path

import cv2
import numpy as np
import yaml
from sacred import Ingredient

from .filter_scene import filter_scene
from .inference_marigold import inference_marigold
from .reconstruction import reconstruction
from .target_horizontals import target_horizontals


pipeline = Ingredient(
	"marigold_horizontal_leafs",
	ingredients=[filter_scene, inference_marigold, reconstruction, target_horizontals],
)


@pipeline.config
def config():
	image_name = "latest.jpg"
	module_dir = Path(__file__).resolve().parents[1]
	output_dir = str(module_dir / "output" / Path(image_name).stem)
	config_path = str(module_dir / "config.yaml")
	steps = 50
	use_ai = True
	run_reconstruction = False


def _add_artifact(run, output_dir, filename, writer):
	output_path = Path(output_dir) / filename
	output_path.parent.mkdir(parents=True, exist_ok=True)
	writer(output_path)
	if run is not None:
		run.add_artifact(str(output_path), name=filename)


@pipeline.capture
def run_pipeline(
	image,
	image_name,
	output_dir,
	config_path,
	steps,
	use_ai,
	run_reconstruction,
	_run=None,
):
	image_bgr = np.asarray(image)
	output_dir = Path(output_dir)
	with open(config_path, "r", encoding="utf-8") as handle:
		config_data = yaml.safe_load(handle) or {}

	filtered = filter_scene.run_filter_scene(image=image_bgr, use_ai=use_ai)
	inference = inference_marigold.run_infer_depths_and_normals(
		image=image_bgr,
		output_dir=str(output_dir),
		steps=steps,
		image_name=image_name,
	)
	depth_map = inference["depth"]
	normals = inference["normals"]
	targets = target_horizontals.run_estimate_horizontal_targets(
		image=image_bgr,
		depth_map=depth_map,
		normals=normals,
		config=config_data,
		use_ai=use_ai,
		output_dir=str(output_dir),
		image_name=image_name,
	)

	point_cloud = None
	if run_reconstruction:
		point_cloud = reconstruction.run_create_point_cloud(
			image=image_bgr,
			depth_map=targets["depth_mm"],
			config=config_data,
			output_dir=str(output_dir),
			image_name=image_name,
		)

	stem = Path(image_name).stem
	overlay = targets["overlay"]
	input_path = output_dir / f"{stem}_input.jpg"
	if input_path.exists() and _run is not None:
		_run.add_artifact(str(input_path), name=input_path.name)
	point_cloud_path = output_dir / f"{stem}_point_cloud.ply"
	if point_cloud_path.exists() and _run is not None:
		_run.add_artifact(str(point_cloud_path), name=point_cloud_path.name)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_image.jpg",
		lambda path: cv2.imwrite(str(path), image_bgr),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_overlay.png",
		lambda path: cv2.imwrite(str(path), overlay),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_depth.npy",
		lambda path: np.save(path, depth_map),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_normals.npy",
		lambda path: np.save(path, normals),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_tray_mask.png",
		lambda path: cv2.imwrite(str(path), filtered["tray_mask"]),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_plant_mask.png",
		lambda path: cv2.imwrite(str(path), filtered["plant_mask"]),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_depth_mm.npy",
		lambda path: np.save(path, targets["depth_mm"]),
	)
	_add_artifact(
		_run,
		output_dir,
		f"{stem}_targets.json",
		lambda path: path.write_text(
			json.dumps(targets["targets"], indent=2), encoding="utf-8"
		),
	)

	result = {
		"image": image_bgr,
		"overlay": overlay,
		"depth": depth_map,
		"normals": normals,
		"tray_mask": targets["tray_mask"],
		"plant_mask": targets["plant_mask"],
		"depth_mm": targets["depth_mm"],
		"targets": targets["targets"],
	}
	if point_cloud is not None:
		result["point_cloud"] = point_cloud
	return result
