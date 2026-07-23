import argparse
import numpy as np
import cv2
import open3d as o3d
import os

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
    if len(depth.shape)==3:
        depth= np.squeeze(depth)
    if rgb.shape[:2] != depth.shape[:2]: 
        depth = cv2.resize(depth, (rgb.shape[1], rgb.shape[0]), interpolation=cv2.INTER_NEAREST)

    h, w = depth.shape[:2]

    # Camera parameters import
    cx, cy =config["camera"]["cx"], config["camera"]["cy"]
    fx = config["camera"]["fx"]
    fy =config["camera"]["fy"]

    # creating pixel grid
    u, v = np.meshgrid(np.arange(w), np.arange(h))
    
    u = u.flatten()
    v = v.flatten()
    
    # We change the depthmap to gray scale to have uniform values
    if len(depth.shape) == 3:
        depth = cv2.cvtColor(depth, cv2.COLOR_BGR2GRAY)
        
    
    depth_mm = depth * config["physical"]["plant_height_mm"] +config["physical"]["tray_z_mm"]-config["physical"]["plant_height_mm"]
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

    x=x/1000
    y=y/1000
    z=z/1000

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

def meshing(points,colors,alpha=0.005,decimate_ratio=0.5):
    #Mesh creation from alpha shape method
    mesh = o3d.geometry.TriangleMesh.create_from_point_cloud_alpha_shape(pcd, alpha)
    #Cleaning
    mesh.compute_vertex_normals()
    mesh.remove_degenerate_triangles()
    mesh.remove_unreferenced_vertices()
    print(f"Triangles generated : {len(mesh.triangles):,}".replace(',', ' '))

    # Simple Quadratic decimation to prevent  heavy files
    if decimate_ratio < 1.0:
        target_faces = int(len(mesh.triangles) * decimate_ratio)
        print(f" Quadratic decimation, keeping only {target_faces:,} faces.".replace(',', ' '))
        mesh = mesh.simplify_quadric_decimation(target_number_of_triangles=target_faces)
        mesh.compute_vertex_normals() # Recalcul des normales après la déformation
    return mesh


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert Marigold Depthmap into ply point cloud and meshing")
    parser.add_argument("--rgb", type=str, required=True, help="Path to original image")
    parser.add_argument("--depth", type=str, required=True, help="Path to Marigold Depthmap")
    parser.add_argument("--output", type=str, default="output", help="Path to output folder")
    parser.add_argument("--config", default="config.yaml", help="Configuration of the scene")
    parser.add_argument("--create-mesh",type=bool,default=True, help="Choose to create a mesh or not")
    parser.add_argument("--alpha", type=float,default=0.0005,help="Alpha parameter to the meshing process")
    parser.add_argument("--decimate_ratio", type= float,default=0.5,help="Percentage of original faces to keep after meshing" )
    
    args = parser.parse_args()
    config = {
            "camera": {},
            "physical": {},
        }
    if os.path.exists(args.config):
            import yaml
    
            with open(args.config, "r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle) or {}
                config.update(loaded)
    output_ply=args.output + "/point_cloud.ply"
    output_mes= args.output +"/mesh.obj"
    pcd=create_point_cloud_from_depth(args.rgb, args.depth, args.output, config)
    o3d.io.write_point_cloud(output_ply, pcd)
    if args.create_mesh:
        mesh=meshing(pcd,args.alpha,args.decimate_ratio)
        o3d.io.write_triangle_mesh(output_mes, mesh)



