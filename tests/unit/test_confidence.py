"""Tests for tad.measurement.confidence."""

from __future__ import annotations

from tad.measurement.confidence import compute_confidence, evaluate_status


class TestComputeConfidence:
    def test_exact_match_is_one(self) -> None:
        assert compute_confidence(47.25, 47.25) == 1.0

    def test_at_boundary_is_zero(self) -> None:
        assert compute_confidence(47.25 + 0.5, 47.25, somewhat_ok_band_mm=0.5) == 0.0

    def test_half_delta_is_half(self) -> None:
        value = compute_confidence(47.25 + 0.25, 47.25, somewhat_ok_band_mm=0.5)
        assert abs(value - 0.5) < 1e-9

    def test_past_boundary_clamped_to_zero(self) -> None:
        assert compute_confidence(60.0, 47.25, somewhat_ok_band_mm=0.5) == 0.0

    def test_zero_band_behaviour(self) -> None:
        assert compute_confidence(47.25, 47.25, somewhat_ok_band_mm=0.0) == 1.0
        assert compute_confidence(47.26, 47.25, somewhat_ok_band_mm=0.0) == 0.0


class TestEvaluateStatus:
    def test_pass_on_target(self) -> None:
        assert evaluate_status(47.25, 47.25) == "PASS"

    def test_pass_within_ok_band(self) -> None:
        # Use values well inside the band to avoid float-edge effects
        assert evaluate_status(47.35, 47.25, ok_band_mm=0.2) == "PASS"
        assert evaluate_status(47.15, 47.25, ok_band_mm=0.2) == "PASS"

    def test_review_in_somewhat_ok_band(self) -> None:
        # delta = 0.4, outside ok (0.2), inside somewhat_ok (0.5)
        assert (
            evaluate_status(
                47.65,
                47.25,
                ok_band_mm=0.2,
                somewhat_ok_band_mm=0.5,
                tolerance_min_mm=47.0,
                tolerance_max_mm=48.0,
            )
            == "REVIEW"
        )

    def test_fail_outside_bands(self) -> None:
        result = evaluate_status(
            47.9,
            47.25,
            ok_band_mm=0.2,
            somewhat_ok_band_mm=0.5,
            tolerance_min_mm=47.0,
            tolerance_max_mm=48.0,
        )
        assert result == "FAIL"

    def test_fail_below_tolerance_min(self) -> None:
        assert evaluate_status(46.5, 47.25, tolerance_min_mm=47.0, tolerance_max_mm=47.5) == "FAIL"

    def test_fail_above_tolerance_max(self) -> None:
        assert evaluate_status(48.0, 47.25, tolerance_min_mm=47.0, tolerance_max_mm=47.5) == "FAIL"

    def test_pass_near_ok_boundary(self) -> None:
        # delta just inside ok_band -> PASS
        assert evaluate_status(47.44, 47.25, ok_band_mm=0.2, somewhat_ok_band_mm=0.5) == "PASS"

    def test_review_at_somewhat_ok_boundary(self) -> None:
        assert (
            evaluate_status(
                47.75,
                47.25,
                ok_band_mm=0.2,
                somewhat_ok_band_mm=0.5,
                tolerance_min_mm=47.0,
                tolerance_max_mm=48.0,
            )
            == "REVIEW"
        )
