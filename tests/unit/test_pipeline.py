"""Tests for tad.processing.pipeline -- the full orchestrator."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from tad.processing.models import PipelineInput, PipelineOutput
from tad.processing.pipeline import measure_innermost_diameter

IMAGES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "images"


def _make_synthetic_circle(
    w: int = 600,
    h: int = 600,
    cx: int | None = None,
    cy: int | None = None,
    radius: int = 80,
    *,
    plate_intensity: int = 220,
    hole_intensity: int = 30,
) -> np.ndarray:  # type: ignore[type-arg]
    """Create a synthetic BGR image: bright plate with a dark filled hole.

    The adaptive threshold expects the bushing to be *darker* than the
    surrounding plate, matching the industrial illumination of the real
    trailing arm images.
    """
    img = np.full((h, w, 3), plate_intensity, dtype=np.uint8)
    if cx is None:
        cx = w // 2
    if cy is None:
        cy = h // 2
    cv2.circle(img, (cx, cy), radius, (hole_intensity, hole_intensity, hole_intensity), -1)
    return img


def _input_for_target(
    image: np.ndarray,  # type: ignore[type-arg]
    *,
    target_diameter_mm: float,
    mm_per_px: float = 0.1,
    radius_tolerance_mm: float = 1.0,
    ok_band_mm: float = 0.2,
    somewhat_ok_band_mm: float = 0.5,
    tolerance_min_mm: float | None = None,
    tolerance_max_mm: float | None = None,
) -> PipelineInput:
    tol_min = tolerance_min_mm if tolerance_min_mm is not None else target_diameter_mm - 2.0
    tol_max = tolerance_max_mm if tolerance_max_mm is not None else target_diameter_mm + 2.0
    return PipelineInput(
        image_bgr=image,
        calibration_mm_per_px=mm_per_px,
        algo_params_version="test",
        target_diameter_mm=target_diameter_mm,
        radius_tolerance_mm=radius_tolerance_mm,
        ok_band_mm=ok_band_mm,
        somewhat_ok_band_mm=somewhat_ok_band_mm,
        tolerance_min_mm=tol_min,
        tolerance_max_mm=tol_max,
        hough_param2=15,
    )


class TestPipelineEndToEnd:
    def test_synthetic_circle_detected(self) -> None:
        # radius=80 px at mm_per_px=0.1 -> diameter 16.0 mm
        img = _make_synthetic_circle(radius=80)
        inp = _input_for_target(img, target_diameter_mm=16.0)
        out = measure_innermost_diameter(inp)

        assert out.error_code is None
        assert out.diameter_mm is not None
        assert abs(out.diameter_mm - 16.0) < 0.5
        assert out.status in ("PASS", "REVIEW")
        assert out.circle is not None

    def test_diameter_accuracy(self) -> None:
        img = _make_synthetic_circle(radius=80)
        inp = _input_for_target(img, target_diameter_mm=16.0)
        out = measure_innermost_diameter(inp)

        assert out.diameter_mm is not None
        # Should be accurate to well under 1 mm on a synthetic image
        assert abs(out.diameter_mm - 16.0) < 0.5

    def test_determinism(self) -> None:
        img = _make_synthetic_circle(radius=80)
        inp = _input_for_target(img, target_diameter_mm=16.0)
        out1 = measure_innermost_diameter(inp)
        out2 = measure_innermost_diameter(inp)
        assert out1.diameter_mm == out2.diameter_mm
        assert out1.status == out2.status
        assert out1.circle == out2.circle
        assert out1.confidence == out2.confidence

    def test_no_circle_on_blank(self) -> None:
        img = np.full((400, 400, 3), 128, dtype=np.uint8)
        inp = _input_for_target(img, target_diameter_mm=16.0)
        out = measure_innermost_diameter(inp)
        assert out.status == "ERROR"
        assert out.error_code == "ERR_NO_CIRCLE"
        assert out.diameter_mm is None

    def test_pass_when_matching_target(self) -> None:
        img = _make_synthetic_circle(radius=80)
        inp = _input_for_target(
            img,
            target_diameter_mm=16.0,
            ok_band_mm=1.0,  # generous band to accept synthetic noise
        )
        out = measure_innermost_diameter(inp)
        assert out.status == "PASS"

    def test_fail_when_outside_absolute_tolerance(self) -> None:
        img = _make_synthetic_circle(radius=80)  # diameter 16.0 mm
        inp = _input_for_target(
            img,
            target_diameter_mm=16.0,
            radius_tolerance_mm=5.0,
            tolerance_min_mm=100.0,  # impossible: measurement will be ~16 mm
            tolerance_max_mm=101.0,
        )
        out = measure_innermost_diameter(inp)
        assert out.status == "FAIL"

    def test_review_in_somewhat_ok_band(self) -> None:
        img = _make_synthetic_circle(radius=80)
        # target 16.5 with ok_band 0.1, somewhat_ok_band 1.0 -> delta ~0.5 -> REVIEW
        inp = _input_for_target(
            img,
            target_diameter_mm=16.5,
            radius_tolerance_mm=2.0,
            ok_band_mm=0.1,
            somewhat_ok_band_mm=1.0,
        )
        out = measure_innermost_diameter(inp)
        assert out.status == "REVIEW"

    def test_annotated_image_same_shape(self) -> None:
        img = _make_synthetic_circle(radius=80)
        inp = _input_for_target(img, target_diameter_mm=16.0)
        out = measure_innermost_diameter(inp)
        assert out.annotated_image.shape == img.shape
        assert out.annotated_image.dtype == np.uint8

    def test_error_output_still_produces_debug_image(self) -> None:
        img = np.full((300, 300, 3), 128, dtype=np.uint8)
        inp = _input_for_target(img, target_diameter_mm=16.0)
        out = measure_innermost_diameter(inp)
        assert out.status == "ERROR"
        assert out.annotated_image is not None
        assert out.annotated_image.shape == img.shape


class TestPipelineWithFixtures:
    """Smoke test against the committed real-image fixtures."""

    def test_fixture_left_runs(self) -> None:
        path = IMAGES_DIR / "cam18jdleofhtlhj6_L.jpg"
        if not path.exists():
            pytest.skip("fixture image not available")
        img = cv2.imread(str(path))
        assert img is not None
        # Real-image target: bushing ~19.8 mm at our calibration
        inp = PipelineInput(
            image_bgr=img,
            calibration_mm_per_px=0.08234,
            algo_params_version="test",
            target_diameter_mm=19.8,
            radius_tolerance_mm=2.0,
            ok_band_mm=1.0,
            somewhat_ok_band_mm=2.5,
            tolerance_min_mm=15.0,
            tolerance_max_mm=25.0,
            hough_param2=15,
        )
        out = measure_innermost_diameter(inp)
        assert isinstance(out, PipelineOutput)
        assert out.annotated_image.shape == img.shape
