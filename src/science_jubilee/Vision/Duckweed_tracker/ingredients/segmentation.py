import cv2
import numpy as np
from sacred import Ingredient

segmentation = Ingredient("segmentation")


@segmentation.config
def config():
    pass


@segmentation.capture
def get_img_contour(img, min_area_px, max_area_px, min_circularity, threshold_green):
    """ExG segmentation — returns contours matching area and circularity filters."""
    r, g, b = cv2.split(img)
    exg = 2 * g.astype(np.int16) - r.astype(np.int16) - b.astype(np.int16)
    exg = cv2.normalize(exg, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)

    _, mask = cv2.threshold(exg, threshold_green, 255, cv2.THRESH_BINARY)
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    valid = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_px or area > max_area_px:
            continue
        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        if 4 * np.pi * area / (perimeter**2) >= min_circularity:
            valid.append(cnt)
    return valid
