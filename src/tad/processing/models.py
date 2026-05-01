"""Data models for the measurement pipeline.

All models are frozen dataclasses — lightweight and immutable.
Pydantic is reserved for API/config boundaries; the hot path uses plain
dataclasses to avoid validation overhead.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import numpy as np


@dataclass(frozen=True)
class InnerCircle:
    """A detected circle with centre and radius."""

    cx: int
    cy: int
    radius_px: float
    peak: float = 0.0  # Hough accumulator strength (0-1 normalised, informational)


@dataclass(frozen=True)
class PipelineInput:
    """Everything the pipeline needs to produce a measurement.

    The contour-based detector needs a target diameter to know which
    scale of circle to look for.  The tolerance bands in ``tolerance_*``
    drive the PASS / REVIEW / FAIL classification.
    """

    image_bgr: np.ndarray[Any, Any]
    calibration_mm_per_px: float
    algo_params_version: str

    # Preprocessing
    blur_kernel: int = 5

    # Adaptive threshold
    threshold_block_size: int = 51
    threshold_c: int = 10

    # Morphology
    morph_kernel_size: int = 3
    morph_iterations: int = 1

    # Contour filter
    contour_min_area: float = 50.0

    # Target diameter + Hough radius window
    target_diameter_mm: float = 47.25
    radius_tolerance_mm: float = 0.3

    # Hough tuning
    hough_dp: float = 1.2
    hough_min_dist: int = 10
    hough_param1: int = 50
    hough_param2: int = 20

    # Classification bands (absolute delta from target in mm)
    ok_band_mm: float = 0.2
    somewhat_ok_band_mm: float = 0.5

    # Absolute tolerance bounds (FAIL if outside, from TRD 5.1)
    tolerance_min_mm: float = 47.0
    tolerance_max_mm: float = 47.5


@dataclass(frozen=True)
class PipelineOutput:
    """Result of running the measurement pipeline on a single image."""

    diameter_mm: float | None
    status: Literal["PASS", "FAIL", "REVIEW", "ERROR"]
    confidence: float | None
    circle: tuple[int, int, float] | None  # (cx, cy, radius_px)
    error_code: str | None
    annotated_image: np.ndarray[Any, Any]
