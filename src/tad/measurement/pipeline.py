"""Measurement pipeline orchestrator.

This is the top-level entry point for measuring the innermost circle
diameter from a single image.  It is **pure** — no I/O, no database,
no filesystem, no sessions.  It takes an image and returns a result.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from tad.measurement.annotate import render_debug_image
from tad.measurement.circle_detect import hough_circles, pick_innermost
from tad.measurement.confidence import evaluate_status, score
from tad.measurement.edges import adaptive_canny
from tad.measurement.models import PipelineInput, PipelineOutput
from tad.measurement.preprocessing import clahe, gaussian_blur
from tad.measurement.ransac_refine import refine_subpixel


def measure_innermost_diameter(inp: PipelineInput) -> PipelineOutput:
    """Run the full measurement pipeline on a single image.

    Steps (TRD Section 6):
        1.  Convert to grayscale
        2.  CLAHE contrast normalisation
        3.  Gaussian blur
        4.  Adaptive Canny edge detection
        5.  Hough circle detection
        6.  Pick innermost circle in the central region
        7.  RANSAC sub-pixel refinement
        8.  Confidence scoring
        9.  Status evaluation (PASS / FAIL / REVIEW / ERROR)
        10. Render annotated debug image

    Parameters
    ----------
    inp:
        A :class:`PipelineInput` containing the image, calibration,
        and algorithm parameters.

    Returns
    -------
    PipelineOutput
        The measurement result, always including an annotated debug image.
    """
    # Step 1: grayscale
    gray = cv2.cvtColor(inp.image_bgr, cv2.COLOR_BGR2GRAY)

    # Step 2: CLAHE
    norm = clahe(gray, inp.clahe_clip_limit, inp.clahe_tile_grid_size)

    # Step 3: Gaussian blur
    blurred = gaussian_blur(norm, inp.blur_kernel)

    # Step 4: adaptive Canny
    edges = adaptive_canny(blurred, inp.canny_lower_ratio, inp.canny_upper_ratio)

    # Step 5: Hough circle detection
    circles = hough_circles(
        blurred,
        dp=inp.hough_dp,
        min_dist=inp.hough_min_dist,
        param1=inp.hough_param1,
        param2=inp.hough_param2,
        min_radius=inp.hough_min_radius_px,
        max_radius=inp.hough_max_radius_px,
    )

    if circles is None or len(circles[0]) == 0:
        return _error(inp, "ERR_NO_CIRCLE", "no circles detected", all_circles=None)

    # Step 6: pick innermost in the central region
    inner = pick_innermost(circles, inp.image_bgr.shape, inp.center_inner_fraction)

    if inner is None:
        return _error(inp, "ERR_NO_CIRCLE", "no circle centred inside region", all_circles=circles)

    # Step 7: RANSAC sub-pixel refinement
    refined, ransac_residual = refine_subpixel(
        edges,
        inner,
        iterations=inp.ransac_iterations,
        inlier_threshold_px=inp.ransac_inlier_threshold_px,
        rng_seed=inp.ransac_seed,
    )

    # Step 8: confidence
    conf = score(hough_peak=inner.peak, ransac_residual=ransac_residual)

    # Step 9: diameter and status
    diameter_mm = 2.0 * refined.radius_px * inp.calibration_mm_per_px
    status = evaluate_status(
        diameter_mm,
        conf,
        conf_pass=inp.conf_pass,
        conf_review=inp.conf_review,
        tolerance_min_mm=inp.tolerance_min_mm,
        tolerance_max_mm=inp.tolerance_max_mm,
    )

    # Step 10: annotated debug image
    annotated = render_debug_image(
        inp.image_bgr, refined, diameter_mm, status, conf, all_circles=circles
    )

    return PipelineOutput(
        diameter_mm=diameter_mm,
        status=status,
        confidence=conf,
        circle=(refined.cx, refined.cy, refined.radius_px),
        error_code=None,
        annotated_image=annotated,
    )


def _error(
    inp: PipelineInput,
    code: str,
    message: str,
    *,
    all_circles: np.ndarray[Any, Any] | None,
) -> PipelineOutput:
    """Build an ERROR output with a debug image showing what went wrong."""
    annotated = render_debug_image(
        inp.image_bgr,
        circle=None,
        diameter_mm=None,
        status="ERROR",
        confidence=None,
        all_circles=all_circles,
    )
    return PipelineOutput(
        diameter_mm=None,
        status="ERROR",
        confidence=None,
        circle=None,
        error_code=code,
        annotated_image=annotated,
    )
