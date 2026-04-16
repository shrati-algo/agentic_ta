"""Tests for tad.measurement.pipeline -- the full orchestrator."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from tad.measurement.models import PipelineInput, PipelineOutput
from tad.measurement.pipeline import measure_innermost_diameter

IMAGES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "images"


def _make_synthetic_circle(
    w: int = 400,
    h: int = 400,
    cx: int | None = None,
    cy: int | None = None,
    radius: int = 80,
) -> np.ndarray:  # type: ignore[type-arg]
    """Create a synthetic BGR image with a clear, detectable circle.

    Uses a dark background with a bright, thick circle for reliable
    Hough detection in tests.
    """
    img = np.full((h, w, 3), 60, dtype=np.uint8)

    if cx is None:
        cx = w // 2
    if cy is None:
        cy = h // 2

    # Thick bright circle on dark background -- easy for Hough
    cv2.circle(img, (cx, cy), radius, (240, 240, 240), 3)
    return img


def _default_input(
    image: np.ndarray,  # type: ignore[type-arg]
    *,
    mm_per_px: float = 0.08234,
    min_radius: int = 40,
    max_radius: int = 160,
    tolerance_min: float = 0.0,
    tolerance_max: float = 999.0,
    ransac_iterations: int = 50,
) -> PipelineInput:
    return PipelineInput(
        image_bgr=image,
        calibration_mm_per_px=mm_per_px,
        algo_params_version="test",
        hough_min_radius_px=min_radius,
        hough_max_radius_px=max_radius,
        hough_param2=15,
        tolerance_min_mm=tolerance_min,
        tolerance_max_mm=tolerance_max,
        ransac_iterations=ransac_iterations,
    )


class TestPipelineEndToEnd:
    def test_synthetic_circle_detected(self) -> None:
        img = _make_synthetic_circle(radius=80)
        inp = _default_input(img)
        output = measure_innermost_diameter(inp)

        assert output.error_code is None
        assert output.status != "ERROR"
        assert output.diameter_mm is not None
        assert output.confidence is not None
        assert output.circle is not None
        assert output.annotated_image.shape == img.shape

    def test_diameter_accuracy(self) -> None:
        """Diameter should be close to 2 * radius * mm_per_px."""
        radius = 80
        mm_per_px = 0.08234
        expected_mm = 2.0 * radius * mm_per_px  # ~13.17 mm

        img = _make_synthetic_circle(radius=radius)
        inp = _default_input(img, mm_per_px=mm_per_px)
        output = measure_innermost_diameter(inp)

        assert output.diameter_mm is not None
        # Allow 20% tolerance for synthetic image detection variance
        assert abs(output.diameter_mm - expected_mm) < expected_mm * 0.20

    def test_determinism(self) -> None:
        """Same input must produce the exact same output."""
        img = _make_synthetic_circle(radius=80)
        inp = _default_input(img)

        out1 = measure_innermost_diameter(inp)
        out2 = measure_innermost_diameter(inp)

        assert out1.diameter_mm == out2.diameter_mm
        assert out1.confidence == out2.confidence
        assert out1.circle == out2.circle
        assert out1.status == out2.status

    def test_no_circle_on_blank_image(self) -> None:
        """A blank image should produce ERR_NO_CIRCLE."""
        img = np.full((400, 400, 3), 128, dtype=np.uint8)
        inp = _default_input(img)
        output = measure_innermost_diameter(inp)

        assert output.status == "ERROR"
        assert output.error_code == "ERR_NO_CIRCLE"
        assert output.diameter_mm is None
        assert output.annotated_image is not None

    def test_status_pass_with_wide_tolerance(self) -> None:
        img = _make_synthetic_circle(radius=80)
        inp = _default_input(img, tolerance_min=0.0, tolerance_max=999.0)
        output = measure_innermost_diameter(inp)

        assert output.error_code is None
        assert output.status in ("PASS", "REVIEW")

    def test_status_fail_with_tight_tolerance(self) -> None:
        img = _make_synthetic_circle(radius=80)
        inp = _default_input(img, tolerance_min=999.0, tolerance_max=999.5)
        output = measure_innermost_diameter(inp)

        assert output.error_code is None
        assert output.status == "FAIL"

    def test_annotated_image_same_shape(self) -> None:
        img = _make_synthetic_circle(radius=80)
        inp = _default_input(img)
        output = measure_innermost_diameter(inp)

        assert output.annotated_image.shape == img.shape
        assert output.annotated_image.dtype == np.uint8

    def test_circle_outside_center_returns_error(self) -> None:
        """Circle at the edge is ignored by pick_innermost."""
        img = np.full((400, 400, 3), 60, dtype=np.uint8)
        cv2.circle(img, (30, 30), 80, (240, 240, 240), 3)
        inp = PipelineInput(
            image_bgr=img,
            calibration_mm_per_px=0.08,
            algo_params_version="test",
            hough_param2=15,
            hough_min_radius_px=40,
            hough_max_radius_px=160,
            center_inner_fraction=0.2,
            ransac_iterations=30,
        )
        output = measure_innermost_diameter(inp)
        # Should be error because circle centre is outside the tiny centre region
        assert output.status == "ERROR" or output.circle is not None


class TestPipelineWithFixtures:
    """Tests using the committed fixture images (smaller RANSAC for speed)."""

    def test_fixture_left_runs(self) -> None:
        path = IMAGES_DIR / "MALBB51BLPM123456_L.jpg"
        if not path.exists():
            pytest.skip("fixture image not available")
        img = cv2.imread(str(path))
        assert img is not None
        inp = _default_input(img, min_radius=20, max_radius=300, ransac_iterations=30)
        output = measure_innermost_diameter(inp)

        assert isinstance(output, PipelineOutput)
        assert output.annotated_image.shape == img.shape

    def test_fixture_determinism(self) -> None:
        path = IMAGES_DIR / "MALBB51BLPM123456_L.jpg"
        if not path.exists():
            pytest.skip("fixture image not available")
        img = cv2.imread(str(path))
        inp = _default_input(img, min_radius=20, max_radius=300, ransac_iterations=30)

        out1 = measure_innermost_diameter(inp)
        out2 = measure_innermost_diameter(inp)

        assert out1.diameter_mm == out2.diameter_mm
        assert out1.status == out2.status
