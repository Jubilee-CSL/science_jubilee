import logging
from pathlib import Path

import cv2
from sacred import Ingredient

from .float_detection import float_detection, get_float_points
from .isolated_duckweed import detect_isolated_duckweed, isolated_duckweed
from .localization import get_lens_position, localization
from .pose_estimation import estimate_float_pose, pose_estimation

logger = logging.getLogger(__name__)

pipeline = Ingredient(
    "pipeline",
    ingredients=[float_detection, pose_estimation, isolated_duckweed, localization],
)


@pipeline.config
def config():
    pass


@pipeline.capture
def run_pipeline(img, camera, output_dir):
    """Full duckweed tracking pipeline — returns (duckweed_3d, float_center_3d)."""
    output_img = img.copy()

    try:
        float_det = get_float_points(img)
        tvec = estimate_float_pose(camera, float_det.points)
        water_level = tvec[2]
        float_center_3d = tvec

        for pt in float_det.points:
            cv2.circle(output_img, (int(pt[0]), int(pt[1])), 4, (0, 255, 255), -1)
        cv2.circle(
            output_img, float_det.center_px, int(float_det.radius_px), (0, 255, 255), 2
        )
        cv2.circle(output_img, float_det.center_px, 5, (255, 0, 0), -1)
        cv2.putText(
            output_img,
            f"Float {float_center_3d}",
            (float_det.center_px[0] + 10, float_det.center_px[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 0, 0),
            2,
        )
    except Exception as exc:
        logger.error("Float detection failed: %s", exc)
        return None, None, None

    duckweed_pixel = detect_isolated_duckweed(img, float_points=float_det.points)
    duckweed_3d = None

    if duckweed_pixel:
        duckweed_3d = get_lens_position(camera, duckweed_pixel, water_level)
        cv2.circle(output_img, duckweed_pixel, 5, (0, 0, 255), -1)
        cv2.putText(
            output_img,
            f"Target {duckweed_3d}",
            (duckweed_pixel[0] + 10, duckweed_pixel[1]),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 255),
            2,
        )
    else:
        logger.warning("No isolated duckweed found.")

    cv2.putText(
        output_img,
        f"Depth Z: {water_level:.1f} mm",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (255, 0, 0),
        2,
    )

    out_path = Path(output_dir) / "latest.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), output_img)
    logger.info("Control image saved: %s", out_path)

    return duckweed_3d, float_center_3d, str(out_path)
