from sacred import Ingredient

import cv2
import numpy as np
from pathlib import Path

from ..src import segment_and_target


target_horizontals = Ingredient("target_horizontals")


@target_horizontals.config
def config():
	use_ai = True


@target_horizontals.capture
def run_estimate_horizontal_targets(
	image,
	depth_map,
	normals,
	config,
	use_ai,
	output_dir,
	image_name="image.jpg",
):
	image_bgr = np.asarray(image)
	output_path = Path(output_dir)
	output_path.mkdir(parents=True, exist_ok=True)
	stem = Path(image_name).stem
	image_path = output_path / f"{stem}_input.jpg"
	depth_path = output_path / f"{stem}_depth.npy"
	normals_path = output_path / f"{stem}_normals.npy"
	cv2.imwrite(str(image_path), image_bgr)
	np.save(depth_path, np.asarray(depth_map))
	np.save(normals_path, np.asarray(normals))
	targets, tray_mask, plant_mask, depth_mm = (
		segment_and_target.estimate_horizontal_targets(
			str(image_path),
			str(depth_path),
			str(normals_path),
			config,
			use_ai=use_ai,
		)
		)

	overlay = image_bgr.copy()
	for target in targets:
		u, v = target["pixel"]
		cv2.circle(overlay, (u, v), 8, (0, 0, 255), -1)
		cv2.putText(
			overlay,
			str(target["id"]),
			(u + 8, v - 8),
			cv2.FONT_HERSHEY_SIMPLEX,
			0.5,
			(0, 0, 255),
			1,
			cv2.LINE_AA,
		)

	return {
		"targets": targets,
		"image": image_bgr,
		"overlay": overlay,
		"tray_mask": tray_mask,
		"plant_mask": plant_mask,
		"depth_mm": depth_mm,
	}
