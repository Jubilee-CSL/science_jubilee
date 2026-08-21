import logging

import cv2
import numpy as np
from sacred import Ingredient

from .segmentation import get_img_contour, segmentation

logger = logging.getLogger(__name__)

isolated_duckweed = Ingredient("isolated_duckweed", ingredients=[segmentation])


@isolated_duckweed.capture
def detect_isolated_duckweed(img,marge, float_points, valid_contours=None):
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
            duck = np.array([cx, cy])
            dist = np.sqrt(np.sum((duck - float_center_2d) ** 2))
            if (dist) / circumference <= 0.75:
                (_, _), radius = cv2.minEnclosingCircle(cnt)
                centers.append(((cx, cy), float(radius)))

    if not centers:
        return None
    if len(centers) == 1:
        return centers[0][0]

    max_min_gap = -float("inf")
    isolated_lens = None

    for i, (center, radius) in enumerate(centers):
        min_gap = float("inf")
        for j, (other, other_radius) in enumerate(centers):
            if i == j:
                continue
            dist = np.linalg.norm(np.array(center) - np.array(other))
            gap = dist - radius - other_radius
            if gap < min_gap:
                min_gap = gap

        if min_gap > max_min_gap:
            max_min_gap = min_gap
            isolated_lens = center

    if max_min_gap < marge:
            logger.warning(
                f"Aucune lentille suffisamment isolée trouvée: meilleur écart {max_min_gap:.1f} < marge {marge}"
            )
            return None

    return isolated_lens
