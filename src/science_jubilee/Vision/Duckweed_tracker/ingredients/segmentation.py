import importlib
import importlib.util
import logging

import cv2
import numpy as np
from sacred import Ingredient

segmentation = Ingredient("segmentation")

logger = logging.getLogger(__name__)

__all__ = [
    "segmentation",
    "get_img_contour",
    "get_img_contour_cellpose",
    "is_cellpose_available",
]


@segmentation.config
def config():
    min_area_px = 10
    max_area_px = 500
    min_circularity = 0.5
    threshold_green = 160
    cellpose_diameter = 8


@segmentation.capture
def get_img_contour(img, min_area_px, max_area_px, min_circularity, threshold_green):
    """ExG segmentation — returns contours matching area and circularity filters."""
    b, g, r = cv2.split(img)
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


def get_img_contour_cellpose(
    img, diameter=8, min_area_px=10, max_area_px=300, min_circularity=0.5
):
    """Cellpose segmentation — returns area-filtered contours.

    If Cellpose is unavailable or inference fails, returns an empty list.
    """
    try:
        models = importlib.import_module("cellpose.models")
    except Exception:
        logger.warning("Cellpose is not installed; AI segmentation disabled.")
        return []

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    try:
        try:
            use_gpu = bool(models.use_gpu())
        except Exception:
            use_gpu = False

        model = models.CellposeModel(gpu=use_gpu, model_type="cyto2")
        masks, flows, styles = model.eval(img_rgb, diameter=diameter, channels=[2, 0])
    except Exception as exc:
        logger.warning("Cellpose inference failed: %s", exc)
        return []

    valid_contours = []
    num_cells = masks.max()
    for i in range(1, num_cells + 1):
        cell_mask = np.uint8(masks == i) * 255
        contours, _ = cv2.findContours(
            cell_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < min_area_px or area > max_area_px:
                continue
            valid_contours.append(cnt)

    return valid_contours


def is_cellpose_available():
    """Return True when Cellpose can be imported in the current environment."""
    return importlib.util.find_spec("cellpose") is not None
