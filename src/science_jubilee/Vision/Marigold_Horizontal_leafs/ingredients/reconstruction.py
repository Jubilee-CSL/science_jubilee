from sacred import Ingredient

import numpy as np
from pathlib import Path
import importlib

import cv2

reconstruction_src = importlib.import_module(
	"science_jubilee.Vision.Marigold_Horizontal_leafs.src.3d_reconstruction"
)


reconstruction = Ingredient("reconstruction")


@reconstruction.config
def config():
	enabled = False


@reconstruction.capture
def run_create_point_cloud(
	image, depth_map, config, output_dir: str, image_name: str = "image.jpg"
):
	output_path = Path(output_dir)
	output_path.mkdir(parents=True, exist_ok=True)
	stem = Path(image_name).stem
	image_path = output_path / f"{stem}_input.jpg"
	depth_path = output_path / f"{stem}_depth_mm.npy"
	point_cloud_path = output_path / f"{stem}_point_cloud.ply"
	cv2.imwrite(str(image_path), np.asarray(image))
	np.save(depth_path, np.asarray(depth_map))
	point_cloud = reconstruction_src.create_point_cloud_from_depth(
		str(image_path),
		str(depth_path),
		str(output_path),
		config,
	)
	import open3d as o3d

	o3d.io.write_point_cloud(str(point_cloud_path), point_cloud)
	return point_cloud
