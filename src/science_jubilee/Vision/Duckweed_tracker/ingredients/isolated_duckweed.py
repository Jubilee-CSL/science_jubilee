import logging

import cv2
import numpy as np
from sacred import Ingredient

from .segmentation import get_img_contour, segmentation

logger = logging.getLogger(__name__)

isolated_duckweed = Ingredient("isolated_duckweed", ingredients=[segmentation])


@isolated_duckweed.config
def config():
    max_distance_ratio = 0.75


@isolated_duckweed.capture
def detect_isolated_duckweed(
    img,
    float_points,
    max_distance_ratio,
    marge,
    valid_contours=None,
    float_contour=None,
    return_filtered_contours=False,
):
    """Return pixel coords of the most isolated duckweed inside the float boundary."""
    if valid_contours is None:
        valid_contours = get_img_contour(img)

    if not valid_contours:
        logger.warning("No duckweed contours detected.")
        return (None, []) if return_filtered_contours else None

    float_center_2d = np.mean(float_points, axis=0)
    circumference = np.abs(float_points[0][0] - float_center_2d[0])

    centers = []
    filtered_contours = []
    for cnt in valid_contours:
        M = cv2.moments(cnt)
        if M["m00"] != 0:
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            if float_contour is not None:
                if (
                    cv2.pointPolygonTest(float_contour, (float(cx), float(cy)), False)
                    < 0
                ):
                    continue
            else:
                duck = np.array([cx, cy])
                dist = np.sqrt(np.sum((duck - float_center_2d) ** 2))
                if dist / circumference > max_distance_ratio:
                    continue

            (_, _), radius = cv2.minEnclosingCircle(cnt)
            centers.append(((cx, cy), float(radius)))
            filtered_contours.append(cnt)

    if not centers:
        return (None, filtered_contours) if return_filtered_contours else None
    if len(centers) == 1:
        return (
            (centers[0][0], filtered_contours)
            if return_filtered_contours
            else centers[0][0]
        )

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
            "Aucune lentille suffisamment isolée trouvée: meilleur écart %.1f < marge %s",
            max_min_gap,
            marge,
        )
        return (None, filtered_contours) if return_filtered_contours else None

    return (
        (isolated_lens, filtered_contours)
        if return_filtered_contours
        else isolated_lens
    )
