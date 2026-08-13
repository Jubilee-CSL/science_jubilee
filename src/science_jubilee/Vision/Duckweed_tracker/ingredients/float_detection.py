from dataclasses import dataclass

import cv2
import numpy as np
from sacred import Ingredient

float_detection = Ingredient("float_detection")


@dataclass
class FloatCircle:
    points: np.ndarray  # 4 cardinal image points for PnP
    center_px: tuple  # (x, y) pixel centre
    radius_px: float  # enclosing circle radius in pixels
    contour: np.ndarray  # contour of detected float in image space


@float_detection.config
def config():
    threshold_blue = 150
    min_area_px = 250
    min_circularity = 0.7


@float_detection.capture
def get_float_points(img, threshold_blue, min_area_px, min_circularity) -> FloatCircle:
    """ExB segmentation — returns FloatCircle with cardinal PnP points, centre and radius."""
    r, g, b = cv2.split(img)
    exb = 2 * b.astype(np.int16) - g.astype(np.int16) - r.astype(np.int16)
    exb = cv2.normalize(exb, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    _, mask = cv2.threshold(exb, threshold_blue, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_contours = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_px:
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * np.pi * area / (perimeter**2)
        if circularity >= min_circularity:
            valid_contours.append(cnt)

    if not valid_contours:
        raise ValueError("No float detected — adjust float_detection config.")

    biggest = max(valid_contours, key=cv2.contourArea)
    (x, y), radius = cv2.minEnclosingCircle(biggest)
    points = np.array(
        [
            [x - radius, y],
            [x, y - radius],
            [x + radius, y],
            [x, y + radius],
        ],
        dtype=np.float32,
    )
    return FloatCircle(
        points=points,
        center_px=(int(x), int(y)),
        radius_px=float(radius),
        contour=biggest,
    )
