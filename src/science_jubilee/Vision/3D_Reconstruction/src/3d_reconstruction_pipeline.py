import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import open3d as o3d

SRC_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = SRC_ROOT.parent


def _windows_to_wsl_path(windows_path: str) -> str:
    path = Path(windows_path).resolve()
    drive_letter = path.drive.rstrip(':').lower()
    return "/mnt/" + drive_letter + path.as_posix()[2:]

for path in (SRC_ROOT, REPO_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

import filter_plants
import meshing
import scale

from science_jubilee.hal.motion_driver import MotionDriver
from science_jubilee.hal.tool_changer import ToolChanger
from science_jubilee.hal.transport.http import HTTPTransport
from science_jubilee.navigation.free_navigation import FreeNavigator
from science_jubilee.tools.camera.toolheadcam import ToolheadCam


def main(num_photos=100, dataset_name="Latest_reconstruction", camera=None,Show=True):
    """Run the full 3D reconstruction pipeline."""
    if num_photos <= 0:
        raise ValueError("num_photos must be a positive integer")

    transport = HTTPTransport(address="10.0.9.6")
    driver = MotionDriver(transport)
    tool_changer = ToolChanger(transport)
    freenav = FreeNavigator(driver,tool_changer)

    dataset_path = REPO_ROOT / "src/science_jubilee/Vision/3D_Reconstruction/Datasets" / dataset_name
    images_dir = dataset_path / "input"
    output_path = REPO_ROOT / "src/science_jubilee/Vision/3D_Reconstruction/Outputs" / f"{dataset_name}_results"

    images_dir.mkdir(parents=True, exist_ok=True)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if camera is None:
        camera = Camera(driver, tool_changer)

    grid_size = int(np.ceil(np.sqrt(num_photos)))
    start_x = 94.0
    start_y = 35.0
    finish_x = 200.0
    finish_y = 265.0

    if grid_size == 1:
        step_x = 0.0
        step_y = 0.0
    else:
        step_x = (finish_x - start_x) / (grid_size - 1)
        step_y = (finish_y - start_y) / (grid_size - 1)

    freenav.move_to(z=320)
    freenav.move_to(x=start_x, y=start_y)

    image_index = 0
    for row in range(grid_size):
        for col in range(grid_size):
            if image_index >= num_photos:
                break

            time.sleep(2)
            img = camera.get_image()
            image_name = f"img_x{start_x + col * step_x}_y{start_y + row * step_y}.jpg"
            cv2.imwrite(str(images_dir / image_name), img)

            if col < grid_size - 1:
                freenav.jog(y=step_y)

            image_index += 1

        if image_index >= num_photos:
            break

        freenav.move_to(y=start_y)
        if row < grid_size - 1:
            freenav.jog(x=step_x)
    
    script_wsl_path = REPO_ROOT / "src/science_jubilee/Vision/3D_Reconstruction/src" / "run_pipeline_ubuntu.sh"
    print(script_wsl_path)
    if not script_wsl_path.exists():
        raise FileNotFoundError(f"WSL pipeline script not found: {script_wsl_path}")

    output_reconstruction = output_path / "3d_reconstruction"

    script_wsl_path_wsl = _windows_to_wsl_path(str(script_wsl_path))
    dataset_path_wsl = _windows_to_wsl_path(str(dataset_path))
    output_reconstruction_wsl = _windows_to_wsl_path(str(output_reconstruction))

    commande = (
        f'start /wait cmd /c "wsl bash {script_wsl_path_wsl} '
        f'--dataset {dataset_path_wsl} '
        f'--output {output_reconstruction_wsl} '
        f'--iterations 10000"'
    )

    print("Gaussian training via WSL...")
    result = os.system(commande)
    if result != 0:
        raise RuntimeError(f"WSL reconstruction failed with exit code {result}")
    
    output_reconstruction = output_path / "3d_reconstruction"
    
    ply_path = output_reconstruction / "point_cloud/iteration_10000" / "point_cloud.ply"
    if not ply_path.exists():
        raise FileNotFoundError(f"Expected point cloud not found: {ply_path}")
    
    filtered_ply_path = output_reconstruction / "point_cloud/iteration_35000" / "point_cloud.ply"
    os.makedirs(filtered_ply_path.parent, exist_ok=True)

    filter_plants.filter_gaussians(
        input_ply=str(ply_path),
        output_ply=str(filtered_ply_path),
        bbox_size=40,  
        bbox_center=[0.0,2,0.0],
        elongation_threshold=7.0,
        scale_threshold=1,
        std_ratio=3,
        opacity_threshold=0.05,
        nb_neighbors=40,
        ban_hue_min=10,
        ban_hue_max=30,
        white_val_thresh=0.05,
    )

    # Step 3: Scaling by extracting the green Aruco codes and scaling and rotating thanks to them, then it references to the blue cube to scale its z axis
    scaled_ply_path = output_reconstruction / "point_cloud/iteration_35000" / "point_cloud_scaled.ply"
    scale.process_and_align(input_ply=str(filtered_ply_path), output_ply=str(scaled_ply_path))

    # Step 4: Meshing
    mesh_path = output_path / "mesh.obj"
    mesh_path.parent.mkdir(parents=True, exist_ok=True)
    meshing.create_mesh_with_alpha_shape(input_ply=scaled_ply_path, output_obj=mesh_path,alpha=0.005, decimate_ratio= 0.6)

    if Show:
        Viewer_path = REPO_ROOT / "src/science_jubilee/Vision/3D_Reconstruction/Viewer/bin"
        #Gaussian Viewer
        os.system(f"cd {Viewer_path} && SIBR_gaussianViewer_app.exe -m {output_reconstruction }")
        #Display the mesh
        mesh = o3d.io.read_triangle_mesh(str(mesh_path))
        o3d.visualization.draw_geometries([mesh], mesh_show_back_face=True)
    

if __name__ == "__main__":
    main(num_photos=50, dataset_name="Plante_test_6", Show=True)
