"""Tests for tad.measurement.confidence."""

from __future__ import annotations

from tad.measurement.confidence import evaluate_status, score


class TestScore:
    def test_perfect_inputs(self) -> None:
        assert score(hough_peak=1.0, ransac_residual=0.0) == 1.0

    def test_zero_peak(self) -> None:
        assert score(hough_peak=0.0, ransac_residual=0.0) == 0.0

    def test_full_residual(self) -> None:
        assert score(hough_peak=1.0, ransac_residual=1.0) == 0.0

    def test_typical_values(self) -> None:
        result = score(hough_peak=1.0, ransac_residual=0.1)
        assert abs(result - 0.9) < 0.01

    def test_clamped_to_0_1(self) -> None:
        assert score(hough_peak=2.0, ransac_residual=-1.0) <= 1.0
        assert score(hough_peak=-1.0, ransac_residual=0.0) >= 0.0


class TestEvaluateStatus:
    def test_pass(self) -> None:
        assert evaluate_status(47.25, 0.90) == "PASS"

    def test_fail_below_tolerance(self) -> None:
        assert evaluate_status(46.5, 0.95) == "FAIL"

    def test_fail_above_tolerance(self) -> None:
        assert evaluate_status(48.0, 0.95) == "FAIL"

    def test_review_low_confidence(self) -> None:
        assert evaluate_status(47.25, 0.70) == "REVIEW"

    def test_error_very_low_confidence(self) -> None:
        assert evaluate_status(47.25, 0.50) == "ERROR"

    def test_boundary_pass_confidence(self) -> None:
        assert evaluate_status(47.25, 0.85) == "PASS"

    def test_boundary_review_confidence(self) -> None:
        assert evaluate_status(47.25, 0.60) == "REVIEW"

    def test_boundary_tolerance_min(self) -> None:
        assert evaluate_status(47.0, 0.90) == "PASS"

    def test_boundary_tolerance_max(self) -> None:
        assert evaluate_status(47.5, 0.90) == "PASS"

    def test_just_below_tolerance_min(self) -> None:
        assert evaluate_status(46.999, 0.90) == "FAIL"

    def test_just_above_tolerance_max(self) -> None:
        assert evaluate_status(47.501, 0.90) == "FAIL"

    def test_custom_thresholds(self) -> None:
        result = evaluate_status(
            50.0,
            0.95,
            tolerance_min_mm=49.0,
            tolerance_max_mm=51.0,
            conf_pass=0.80,
            conf_review=0.50,
        )
        assert result == "PASS"
