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
    peak: float = 0.0  # Hough accumulator strength (0-1 normalised)


@dataclass(frozen=True)
class PipelineInput:
    """Everything the pipeline needs to produce a measurement."""

    image_bgr: np.ndarray[Any, Any]
    calibration_mm_per_px: float
    algo_params_version: str

    # Unpacked algo_params (avoids importing config models into the pure layer)
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: tuple[int, int] = (8, 8)
    blur_kernel: int = 5
    canny_lower_ratio: float = 0.66
    canny_upper_ratio: float = 1.33
    hough_dp: float = 1.2
    hough_min_dist: int = 40
    hough_param1: int = 100
    hough_param2: int = 30
    hough_min_radius_px: int = 40
    hough_max_radius_px: int = 160
    center_inner_fraction: float = 0.7
    ransac_iterations: int = 200
    ransac_inlier_threshold_px: float = 1.0
    ransac_seed: int = 42
    conf_pass: float = 0.85
    conf_review: float = 0.60
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
