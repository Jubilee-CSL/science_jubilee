import cv2
import numpy as np
from sacred import Ingredient

localization = Ingredient("localization")


@localization.capture
def get_lens_position(camera, lens_pixel, water_level) -> np.ndarray:
    """Unproject a pixel to a 3-D point in the camera frame at the given depth."""
    u, v = lens_pixel
    z = float(water_level)
    undistorted = cv2.undistortPoints(
        np.array([[[u, v]]], dtype=np.float32),
        camera.K,
        np.array(camera.dist, dtype=np.float32),
    )
    x_norm = undistorted[0, 0, 0]
    y_norm = undistorted[0, 0, 1]
    return np.array([x_norm * z, y_norm * z, z], dtype=np.float32)
