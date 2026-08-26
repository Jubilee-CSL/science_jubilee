from sacred import Ingredient
import open3d as o3d
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


def create_point_cloud_from_depth(rgb_path, depth_path, output_ply, config: dict):
    print(f"Loading RGB_path: {rgb_path}")
    print(f"CLoading Depth Map : {depth_path}")

    # Convert to opencv rgb
    rgb = cv2.imread(rgb_path)
    if rgb is None:
        raise ValueError("unable to read the RGB file")
    rgb = cv2.cvtColor(rgb, cv2.COLOR_BGR2RGB)

    # depth_map reading
    depth = np.load(depth_path)
    if len(depth.shape) == 3:
        depth = np.squeeze(depth)
    if rgb.shape[:2] != depth.shape[:2]:
        depth = cv2.resize(
            depth, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST
        )

    h, w = depth.shape[:2]

    # Camera parameters import
    cx, cy = config["camera"]["cx"], config["camera"]["cy"]
    fx = config["camera"]["fx"]
    fy = config["camera"]["fy"]

    # creating pixel grid
    u, v = np.meshgrid(np.arange(w), np.arange(h))

    u = u.flatten()
    v = v.flatten()

    # We change the depthmap to gray scale to have uniform values
    if len(depth.shape) == 3:
        depth = cv2.cvtColor(depth, cv2.COLOR_BGR2GRAY)

    depth_mm = (
        depth * config["physical"]["plant_height_mm"]
        + config["physical"]["tray_z_mm"]
        - config["physical"]["plant_height_mm"]
    )
    z = depth_mm.flatten().astype(np.float32)
    # Filter  valid pixels
    valid = z > 0
    u = u[valid]
    v = v[valid]
    z = z[valid]

    # Pixel reprojection into 3D space thanks to camera pinhole model (2D -> 3D)
    x = (u - cx) * z / fx
    y = (v - cy) * z / fy

    # Axis change to 3d understanding
    y = -y
    z = -z

    x = x / 1000
    y = y / 1000
    z = z / 1000

    points = np.vstack((x, y, z)).T
    colors = rgb.reshape(-1, 3)[valid] / 255.0  # Ore scaling colors for open3d format
    print(f"Point cloud with {len(points)} points...")
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)
    pcd.colors = o3d.utility.Vector3dVector(colors)

    # Noise removal by outliers filtering
    print("Statistical Outlier Removal...")
    pcd, _ = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)

    return pcd



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
	point_cloud = create_point_cloud_from_depth(
		str(image_path),
		str(depth_path),
		str(output_path),
		config,
	)
	import open3d as o3d

	o3d.io.write_point_cloud(str(point_cloud_path), point_cloud)
	return point_cloud
