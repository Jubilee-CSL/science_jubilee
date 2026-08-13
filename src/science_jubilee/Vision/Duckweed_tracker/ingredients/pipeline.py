import logging
import time
from pathlib import Path

import cv2
import numpy as np
from sacred import Ingredient

from .float_detection import float_detection, get_float_points
from .insertion_point import get_insertion_point_2, insertion_point
from .isolated_duckweed import detect_isolated_duckweed, isolated_duckweed
from .localization import get_lens_position, localization
from .pose_estimation import estimate_float_pose, pose_estimation
from .RRT import rrt, rrt_path_planning, smooth_path
from .segmentation import get_img_contour, get_img_contour_cellpose, segmentation

logger = logging.getLogger(__name__)


def _safe_debug_breakpoint(enabled: bool, label: str):
    """Pause execution in ipdb when debug breakpoints are enabled."""
    if not enabled:
        return
    try:
        import importlib

        ipdb = importlib.import_module("ipdb")

        logger.info("Entering ipdb breakpoint: %s", label)
        ipdb.set_trace()
    except Exception as exc:
        logger.info("Debug hook unavailable at '%s': %s", label, exc)


def _write_debug_image(debug_artifacts: dict, key: str, image, out_dir: Path):
    path = out_dir / f"{key}.png"
    cv2.imwrite(str(path), image)
    debug_artifacts[key] = str(path)


pipeline = Ingredient(
    "pipeline",
    ingredients=[
        float_detection,
        segmentation,
        pose_estimation,
        isolated_duckweed,
        insertion_point,
        rrt,
        localization,
    ],
)


@pipeline.config
def config():
    output_dir = str(Path(__file__).resolve().parents[1] / "Filtered_images")
    float_width_mm = 5.0
    insertion_margin_mm = 15.0
    target_margin_mm = 3.0
    tool_radius_mm = 1.27
    water_level_offset_mm = 1.5
    debug_capture = False
    debug_breakpoints = False
    debug_dir = ""


@pipeline.capture
def run_pipeline(
    img,
    camera,
    output_dir,
    threshold_blue,
    min_area_px,
    min_circularity,
    float_radius_mm,
    use_ai,
    cellpose_diameter,
    float_width_mm,
    insertion_margin_mm,
    target_margin_mm,
    tool_radius_mm,
    max_offset_px,
    step_size,
    max_iter,
    goal_sample_rate,
    water_level_offset_mm,
    debug_capture,
    debug_breakpoints,
    debug_dir,
):
    """Duckweed pipeline.

    Returns:
        tuple: (
            duckweed_3d,
            float_center_3d,
            checkpoints_3d,
            control_image_path,
            debug_artifacts,
        )
    """
    output_img = img.copy()
    duckweed_3d = None
    checkpoints_3d = np.empty((0, 3), dtype=np.float32)
    obstacle_mask = None
    mask_for_insertion = None
    debug_artifacts = {}
    run_tag = time.strftime("%Y%m%d_%H%M%S")
    effective_debug_dir = Path(debug_dir) if debug_dir else (Path(output_dir) / "debug")
    effective_debug_dir = effective_debug_dir / run_tag
    if debug_capture:
        effective_debug_dir.mkdir(parents=True, exist_ok=True)
        _write_debug_image(debug_artifacts, "00_raw", img, effective_debug_dir)

    logger.info(
        "Pipeline start | use_ai=%s threshold_blue=%s min_area_px=%s min_circularity=%s",
        use_ai,
        threshold_blue,
        min_area_px,
        min_circularity,
    )
    _safe_debug_breakpoint(debug_breakpoints, "pipeline_start")

    try:
        float_det = get_float_points(
            img,
            threshold_blue=threshold_blue,
            min_area_px=min_area_px,
            min_circularity=min_circularity,
        )
        tvec = estimate_float_pose(
            camera, float_det.points, float_radius_mm=float_radius_mm
        )
        water_level = tvec[2] - float(water_level_offset_mm)
        float_center_3d = tvec

        if float_det.radius_px <= 0:
            raise RuntimeError("Invalid float radius in pixels.")
        mm_per_px = float(float_radius_mm) / float(float_det.radius_px)
        insertion_margin_px = float(insertion_margin_mm) / mm_per_px
        target_margin_px = float(target_margin_mm) / mm_per_px
        tool_radius_px = max(1, int(float(tool_radius_mm) / mm_per_px))
        float_width_px = max(1, int(float(float_width_mm) / mm_per_px))

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
        logger.info(
            "Float detected | center_px=%s radius_px=%.2f water_level=%.2f",
            float_det.center_px,
            float_det.radius_px,
            water_level,
        )
        if debug_capture:
            _write_debug_image(
                debug_artifacts, "01_float_detection", output_img, effective_debug_dir
            )
        _safe_debug_breakpoint(debug_breakpoints, "after_float_detection")
    except Exception as exc:
        logger.error("Float detection failed: %s", exc)
        return None, None, checkpoints_3d, None, {}

    if use_ai:
        valid_contours = get_img_contour_cellpose(img, diameter=cellpose_diameter)
        logger.info(
            "Segmentation mode: Cellpose (AI), contours=%d", len(valid_contours)
        )
    else:
        valid_contours = get_img_contour(img)
        logger.info(
            "Segmentation mode: ExG (classic), contours=%d", len(valid_contours)
        )

    if debug_capture:
        seg_vis = img.copy()
        if valid_contours:
            cv2.drawContours(seg_vis, valid_contours, -1, (0, 255, 0), 2)
        _write_debug_image(
            debug_artifacts, "02_segmentation", seg_vis, effective_debug_dir
        )
    _safe_debug_breakpoint(debug_breakpoints, "after_segmentation")

    duckweed_pixel, float_inner_contours = detect_isolated_duckweed(
        img,
        float_points=float_det.points,
        marge=target_margin_px,
        valid_contours=valid_contours,
        float_contour=float_det.contour,
        return_filtered_contours=True,
    )

    if float_inner_contours:
        cv2.drawContours(output_img, float_inner_contours, -1, (0, 255, 0), 1)
    logger.info(
        "Isolation result | duckweed_pixel=%s inside_float_contours=%d",
        duckweed_pixel,
        len(float_inner_contours),
    )
    if debug_capture:
        _write_debug_image(
            debug_artifacts, "03_isolation", output_img, effective_debug_dir
        )
    _safe_debug_breakpoint(debug_breakpoints, "after_isolation")

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

        roi_mask = np.zeros(img.shape[:2], dtype=np.uint8)
        roi_radius = max(1, int(float_det.radius_px) - float_width_px)
        cv2.circle(roi_mask, float_det.center_px, roi_radius, 255, -1)

        target_cnt = None
        for cnt in valid_contours:
            if cv2.pointPolygonTest(cnt, duckweed_pixel, False) >= 0:
                target_cnt = cnt
                break

        obstacle_mask = np.zeros(img.shape[:2], dtype=np.uint8)
        for cnt in valid_contours:
            if target_cnt is None or cnt is not target_cnt:
                cv2.drawContours(obstacle_mask, [cnt], -1, 255, thickness=cv2.FILLED)

        kernel_size = max(1, tool_radius_px * 2)
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (kernel_size, kernel_size)
        )
        obstacle_mask = cv2.dilate(obstacle_mask, kernel)
        outside_roi = cv2.bitwise_not(roi_mask)
        obstacle_mask = cv2.bitwise_or(obstacle_mask, outside_roi)

        insertion_2d, mask_for_insertion = get_insertion_point_2(
            obstacle_mask=obstacle_mask,
            duckweed_goal=duckweed_pixel,
            marge=insertion_margin_px,
            max_offset_px=max_offset_px,
        )
        cv2.circle(output_img, insertion_2d, 6, (255, 255, 0), -1)
        cv2.putText(
            output_img,
            "Insertion",
            (insertion_2d[0] - 30, insertion_2d[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 0),
            2,
        )

        path_2d = rrt_path_planning(
            start_2d=insertion_2d,
            goal_2d=duckweed_pixel,
            obstacle_mask=obstacle_mask,
            roi_mask=roi_mask,
            marge=target_margin_px,
            step_size=step_size,
            max_iter=max_iter,
            goal_sample_rate=goal_sample_rate,
        )
        if path_2d:
            smoothed_path_2d = smooth_path(path_2d, obstacle_mask)
            points_3d = []
            for i, pt in enumerate(smoothed_path_2d):
                if i < len(smoothed_path_2d) - 1:
                    nxt = smoothed_path_2d[i + 1]
                    corner = (nxt[0], pt[1])
                    cv2.line(output_img, pt, corner, (0, 165, 255), 2)
                    cv2.line(output_img, corner, nxt, (0, 165, 255), 2)
                cv2.circle(output_img, pt, 3, (255, 0, 255), -1)
                points_3d.append(get_lens_position(camera, pt, water_level))
            checkpoints_3d = np.array(points_3d, dtype=np.float32)
            logger.info("Planned path with %d checkpoints.", len(checkpoints_3d))
            logger.info(
                "Path debug | insertion=%s target=%s raw_nodes=%d smoothed_nodes=%d",
                insertion_2d,
                duckweed_pixel,
                len(path_2d),
                len(smoothed_path_2d),
            )
        else:
            logger.warning("No viable RRT path to target.")

        if debug_capture:
            _write_debug_image(
                debug_artifacts, "04_obstacle_mask", obstacle_mask, effective_debug_dir
            )
            _write_debug_image(
                debug_artifacts,
                "05_insertion_mask",
                mask_for_insertion,
                effective_debug_dir,
            )
            _write_debug_image(
                debug_artifacts, "06_path_overlay", output_img, effective_debug_dir
            )
        _safe_debug_breakpoint(debug_breakpoints, "after_path_planning")
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
    debug_artifacts["control"] = str(out_path)

    if obstacle_mask is not None:
        obstacle_path = Path(output_dir) / "latest_obstacle.png"
        cv2.imwrite(str(obstacle_path), obstacle_mask)
        debug_artifacts["obstacle"] = str(obstacle_path)

    if mask_for_insertion is not None:
        insertion_path = Path(output_dir) / "latest_insertion.png"
        cv2.imwrite(str(insertion_path), mask_for_insertion)
        debug_artifacts["insertion"] = str(insertion_path)

    logger.info("Control image saved: %s", out_path)
    _safe_debug_breakpoint(debug_breakpoints, "pipeline_end")

    return duckweed_3d, float_center_3d, checkpoints_3d, str(out_path), debug_artifacts
