import cv2
import numpy as np
from sacred import Ingredient

pose_estimation = Ingredient("pose_estimation")


@pose_estimation.config
def config():
    float_radius_mm = 37.5


@pose_estimation.capture
def estimate_float_pose(camera, image_points, float_radius_mm) -> np.ndarray:
    """PnP pose estimation — returns the translation vector Tcf (X, Y, Z in mm)."""
    object_points = np.array(
        [
            [-float_radius_mm, 0, 0],
            [0, -float_radius_mm, 0],
            [float_radius_mm, 0, 0],
            [0, float_radius_mm, 0],
        ],
        dtype=np.float32,
    )

    ok, rvecs, tvecs, errors = cv2.solvePnPGeneric(
        object_points,
        image_points,
        camera.K,
        camera.dist,
        flags=cv2.SOLVEPNP_IPPE,
    )
    if not ok:
        raise RuntimeError("solvePnPGeneric failed.")

    best, best_err = None, np.inf
    for rvec, tvec, err in zip(rvecs, tvecs, errors):
        if tvec[2][0] > 0 and err < best_err:
            best_err = err
            best = tvec.reshape(3)

    if best is None:
        raise RuntimeError("No valid forward PnP solution (Z > 0).")
    return best
