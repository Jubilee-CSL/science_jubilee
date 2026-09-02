# Horizontal leafs detector
# OLD PIPELINE NEEDS TO BE CHANGED, Use the notebook test_piepline for sacred integration 

This project estimates depth and surface normals from a camera image, isolates the printer tray, detects plant/leaf regions, and exports camera-relative XYZ positions for likely horizontal surfaces.

## Setup on Windows

1. Create and activate the environment
   ```powershell
   conda create -n marigold_env python=3.10 -y
   conda activate marigold_env
   ```

2. Install dependencies
   ```powershell
   conda install pytorch torchvision pytorch-cuda=11.8 -c pytorch -c nvidia -y
   pip install diffusers transformers accelerate omegaconf open_clip_torch opencv-python numpy pillow rembg pyyaml
   ```

# Camera calibration
1. Print "calibration_sheet.pdf" and take different photos with your camera and store them on input/calibration/

2. Change the calibration folder path on calibration.py

3. ```powershell
   python src/calibration.py
   ```

4. Update the camera parameters in config.yaml
   - Set fx, fy, cx, cy from your calibration.
   - Set tray_z_mm to the known tray height above the camera reference plane.

## Run the pipeline

```powershell
python src/segment_and_target.py --image path\to\your_image.jpg --output output --config config.yaml
```

## Outputs

The pipeline writes:
- output/targets.json: detected targets with xyz_mm and normals
- output/overlay_targets.png: annotated image showing the tray mask, plant mask, and detected targets
- output/depth_mm.npy: scaled depth map in millimeters
- output/tray_mask.npy: tray segmentation mask
- output/plant_mask.npy: plant segmentation mask

## Jubilee implemantation

### Launch the full pipeline on the jubilee (need other jubilee pip packages(see science_jubilee/tests/))

Step 1: Change the real "plant_height" on config.yaml and dont forget the camera parameters!

Step 2 : ```powershell
python src/jubilee_horizontal_target.py
         ```


## Notes

- If rembg is unavailable, the script automatically falls back to an HSV-based plant mask.
- The XYZ values are computed in the camera coordinate frame, so they can be used as robot-relative positions after a simple camera-to-robot transform.
- The filtering thresholds are configurable in config.yaml:
  - min_area_px: raise this for larger plants or to keep only big surfaces
  - max_extent_ratio: lower this to reject elongated or spurious blobs
  - min_border_margin_px: increase this to avoid edge artifacts from the segmentation mask
  - min_normal_z and min_normal_confidence: tune the horizontal-surface orientation requirement
  - depth_consistency_max_std_mm and depth_consistency_radius_px: tune the local depth stability requirement
