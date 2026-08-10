import logging

import cv2
import numpy as np
from sacred import Ingredient

from .segmentation import get_img_contour, segmentation

logger = logging.getLogger(__name__)

isolated_duckweed = Ingredient("isolated_duckweed", ingredients=[segmentation])


@isolated_duckweed.capture
def detect_isolated_duckweed(img, float_points, valid_contours=None):
    """Return pixel coords of the most isolated duckweed inside the float boundary."""
    if valid_contours is None:
        valid_contours = get_img_contour(img)

    if not valid_contours:
        logger.warning("No duckweed contours detected.")
        return None

    float_center_2d = np.mean(float_points, axis=0)
    circumference = np.abs(float_points[0][0] - float_center_2d[0])

    centers = []
    for cnt in valid_contours:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            dist = np.sqrt(np.sum((np.array([cx, cy]) - float_center_2d) ** 2))
            if dist / circumference <= 0.8:
                centers.append((cx, cy))

    if not centers:
        return None
    if len(centers) == 1:
        return centers[0]

    # pick the center whose nearest neighbour is farthest away
    max_min_dist = -1
    isolated = None
    for i, c in enumerate(centers):
        min_d = min(
            np.linalg.norm(np.array(c) - np.array(o))
            for j, o in enumerate(centers)
            if j != i
        )
        if min_d > max_min_dist:
            max_min_dist = min_d
            isolated = c
    return isolated
