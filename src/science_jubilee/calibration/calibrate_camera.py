"""
Camera intrinsic calibration using a checkerboard.

Usage
-----
Collect images and calibrate in one step:

    python calibration/calibrate_camera.py --collect --images calibration/images --out calibration/camera_params.yaml

Or calibrate from images you already have:

    python calibration/calibrate_camera.py --images calibration/images --out calibration/camera_params.yaml

After calibration, set in .env.hardware:
    JUBILEE_CAMERA_CALIB=calibration/camera_params.yaml
"""

import argparse
import glob
import os
import sys

import cv2
import numpy as np
import yaml

CHECKERBOARD = (6, 8)


def collect_images(images_folder: str) -> None:
    """Capture calibration images from the machine camera interactively."""
    os.makedirs(images_folder, exist_ok=True)

    from science_jubilee.machine_session import MachineSession
    session = MachineSession.from_env(env_file=".env.hardware")

    limits = session.motion.get_axis_limits()
    BED_CX = sum(limits["X"]) / 2
    BED_CY = sum(limits["Y"]) / 2
    BED_Z = limits["Z"][0] + 300.0  # 300 mm above Z min so board fills frame

    print("Checking homing state...")
    if not session.motion.get_axes_homed() or not all(session.motion.get_axes_homed()):
        print("Homing all axes...")
        session.motion.home_all()
    session.camera.move_to_get_image(BED_CX, BED_CY, BED_Z)

    print(
        "\nReady to collect calibration images."
        f"\n  Camera is at X={BED_CX} Y={BED_CY} Z={BED_Z} mm."
        "\n  Open OctoPrint → Camera tab to preview the live feed."
        "\n  The FULL chessboard must be visible in every shot — no cropped corners."
        "\n  Tilt or rotate the board between shots (vary angle, not just position)."
        "\n  Aim for 15–20 images. Type 'q' + Enter when done.\n"
    )

    idx = 0
    while True:
        user = input(f"  Shot {idx:02d} — Enter to capture, 'q' to finish: ").strip().lower()
        if user == "q":
            break
        img = session.camera.get_image()
        path = os.path.join(images_folder, f"calib_{idx:03d}.jpg")
        cv2.imwrite(path, img)
        print(f"  Saved {path}")
        idx += 1

    print(f"\nCollected {idx} images in '{images_folder}'.")


def calibrate(images_folder: str) -> tuple[np.ndarray, np.ndarray, float]:
    objp = np.zeros((CHECKERBOARD[0] * CHECKERBOARD[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHECKERBOARD[0], 0:CHECKERBOARD[1]].T.reshape(-1, 2)

    objpoints, imgpoints = [], []

    patterns = ("*.jpg", "*.jpeg", "*.png")
    images = []
    for p in patterns:
        images.extend(glob.glob(os.path.join(images_folder, p)))

    if not images:
        raise FileNotFoundError(f"No images found in: {images_folder}")

    print(f"Found {len(images)} images, searching for checkerboard corners...")

    gray = None
    valid = 0
    for fname in images:
        img = cv2.imread(fname)
        if img is None:
            continue
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ret, corners = cv2.findChessboardCorners(gray, CHECKERBOARD, None)
        if ret:
            criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
            corners2 = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            objpoints.append(objp)
            imgpoints.append(corners2)
            valid += 1
            print(f"  [OK]   {os.path.basename(fname)}")
        else:
            print(f"  [SKIP] {os.path.basename(fname)} — corners not found")

    if not objpoints:
        raise ValueError(
            "Checkerboard not detected in any image. "
            f"Check CHECKERBOARD={CHECKERBOARD} matches your board."
        )

    print(f"\nCalibrating with {valid} valid images...")
    rms, mtx, dist, rvecs, tvecs = cv2.calibrateCamera(
        objpoints, imgpoints, gray.shape[::-1], None, None
    )

    # Per-image reprojection error
    errors = []
    for i in range(len(objpoints)):
        projected, _ = cv2.projectPoints(objpoints[i], rvecs[i], tvecs[i], mtx, dist)
        err = np.linalg.norm(imgpoints[i].reshape(-1, 2) - projected.reshape(-1, 2)) / len(projected)
        errors.append(err)
        print(f"  Image {i:2d}: reprojection error = {err:.4f} px")

    print(f"\nRMS error: {rms:.4f} px  (mean per-image: {np.mean(errors):.4f} px)")
    if rms > 1.0:
        print("  Warning: RMS > 1.0 — consider recollecting images.")

    return mtx, dist, rms


def save_params(mtx: np.ndarray, dist: np.ndarray, out_path: str) -> None:
    config = {
        "camera": {
            "fx": float(mtx[0, 0]),
            "fy": float(mtx[1, 1]),
            "cx": float(mtx[0, 2]),
            "cy": float(mtx[1, 2]),
            "dist": dist.flatten().tolist(),
            # Physical offset (mm) from tool tip to camera centre — measure and adjust.
            "offset": [0, -20, 0],
        }
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    print(f"\nSaved to: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collect calibration images and/or calibrate camera.")
    parser.add_argument("--collect", action="store_true", help="Capture images from the machine before calibrating.")
    parser.add_argument("--images", required=True, help="Folder to save/read calibration images.")
    parser.add_argument("--out", default="calibration/camera_params.yaml", help="Output YAML path.")
    parser.add_argument(
        "--checkerboard", nargs=2, type=int, default=list(CHECKERBOARD), metavar=("COLS", "ROWS"),
        help="Inner corner count: columns rows (default: 6 8)."
    )
    args = parser.parse_args()

    CHECKERBOARD = tuple(args.checkerboard)

    try:
        if args.collect:
            collect_images(args.images)
        mtx, dist, rms = calibrate(args.images)
        save_params(mtx, dist, args.out)
        print("\nDone. Set JUBILEE_CAMERA_CALIB=" + args.out)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
