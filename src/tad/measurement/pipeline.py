"""Measurement pipeline orchestrator.

Top-level entry point for measuring the innermost circle diameter from a
single image.  The pipeline is **pure** — no I/O, no database, no
filesystem, no sessions.  It takes an image and returns a result.

Pipeline stages (TRD Section 6):

    1.  BGR -> grayscale
    2.  Gaussian blur
    3.  Adaptive Gaussian threshold (inverted -> holes become foreground)
    4.  Morphological close
    5.  External contour extraction, sorted largest-area first
    6.  For each contour (masked), run cv2.HoughCircles constrained to
        the target radius window (``target_diameter_mm +/- radius_tolerance_mm``)
    7.  First matching circle wins
    8.  Diameter in mm = 2 * radius_px * mm_per_px
    9.  Band classification -> PASS / REVIEW / FAIL
    10. Annotated debug image (detected circle + target reference circle)
"""

from __future__ import annotations

import cv2

from tad.measurement.annotate import render_debug_image
from tad.measurement.confidence import compute_confidence, evaluate_status
from tad.measurement.contour_detect import detect_circle
from tad.measurement.models import PipelineInput, PipelineOutput
from tad.measurement.preprocessing import gaussian_blur
from tad.measurement.threshold import adaptive_threshold, morph_close


def measure_innermost_diameter(inp: PipelineInput) -> PipelineOutput:
    """Run the full measurement pipeline on a single image."""
    # 1. Grayscale
    gray = cv2.cvtColor(inp.image_bgr, cv2.COLOR_BGR2GRAY)

    # 2. Gaussian blur
    blurred = gaussian_blur(gray, inp.blur_kernel)

    # 3. Adaptive threshold (inverted: holes become foreground)
    binary = adaptive_threshold(
        blurred,
        block_size=inp.threshold_block_size,
        c=inp.threshold_c,
    )

    # 4. Morphological close
    cleaned = morph_close(
        binary,
        kernel_size=inp.morph_kernel_size,
        iterations=inp.morph_iterations,
    )

    # 5-7. Contour iteration + masked Hough
    circle = detect_circle(
        gray,
        cleaned,
        mm_per_px=inp.calibration_mm_per_px,
        target_diameter_mm=inp.target_diameter_mm,
        radius_tolerance_mm=inp.radius_tolerance_mm,
        min_contour_area=inp.contour_min_area,
        dp=inp.hough_dp,
        min_dist=inp.hough_min_dist,
        param1=inp.hough_param1,
        param2=inp.hough_param2,
    )

    if circle is None:
        return _error(inp, "ERR_NO_CIRCLE", "no circle matching target radius")

    # 8. Diameter in mm
    diameter_mm = 2.0 * circle.radius_px * inp.calibration_mm_per_px

    # 9. Classification
    status = evaluate_status(
        diameter_mm,
        inp.target_diameter_mm,
        ok_band_mm=inp.ok_band_mm,
        somewhat_ok_band_mm=inp.somewhat_ok_band_mm,
        tolerance_min_mm=inp.tolerance_min_mm,
        tolerance_max_mm=inp.tolerance_max_mm,
    )

    # Confidence is informational: linear in delta from target
    confidence = compute_confidence(
        diameter_mm,
        inp.target_diameter_mm,
        somewhat_ok_band_mm=inp.somewhat_ok_band_mm,
    )

    # 10. Debug image
    annotated = render_debug_image(
        inp.image_bgr,
        circle,
        diameter_mm,
        status,
        confidence,
        target_diameter_mm=inp.target_diameter_mm,
        mm_per_px=inp.calibration_mm_per_px,
    )

    return PipelineOutput(
        diameter_mm=diameter_mm,
        status=status,
        confidence=confidence,
        circle=(circle.cx, circle.cy, circle.radius_px),
        error_code=None,
        annotated_image=annotated,
    )


def _error(
    inp: PipelineInput,
    code: str,
    message: str,
) -> PipelineOutput:
    """Build an ERROR output with a debug image showing what went wrong.

    The ``message`` parameter is accepted for API symmetry and future use
    (embedding it in the annotated image); it is currently unused.
    """
    del message  # reserved for future debug-image inclusion
    annotated = render_debug_image(
        inp.image_bgr,
        circle=None,
        diameter_mm=None,
        status="ERROR",
        confidence=None,
        target_diameter_mm=inp.target_diameter_mm,
        mm_per_px=inp.calibration_mm_per_px,
    )
    return PipelineOutput(
        diameter_mm=None,
        status="ERROR",
        confidence=None,
        circle=None,
        error_code=code,
        annotated_image=annotated,
    )
