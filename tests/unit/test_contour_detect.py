"""Tests for tad.processing.contour_detect."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from tad.processing.contour_detect import (
    _radius_bounds_px,
    detect_circle,
    detect_circle_in_contour,
    find_candidate_contours,
)


class TestFindCandidateContours:
    def test_returns_sorted_largest_first(self) -> None:
        binary = np.zeros((300, 300), dtype=np.uint8)
        cv2.circle(binary, (80, 80), 40, 255, -1)  # large
        cv2.circle(binary, (220, 220), 20, 255, -1)  # medium
        cv2.circle(binary, (220, 80), 5, 255, -1)  # small

        contours = find_candidate_contours(binary, min_area=10.0)
        assert len(contours) == 3
        areas = [cv2.contourArea(c) for c in contours]
        assert areas == sorted(areas, reverse=True)

    def test_min_area_filter(self) -> None:
        binary = np.zeros((300, 300), dtype=np.uint8)
        cv2.circle(binary, (150, 150), 40, 255, -1)
        cv2.circle(binary, (50, 50), 2, 255, -1)  # tiny

        contours = find_candidate_contours(binary, min_area=100.0)
        assert len(contours) == 1

    def test_empty_mask(self) -> None:
        binary = np.zeros((100, 100), dtype=np.uint8)
        assert find_candidate_contours(binary) == []


class TestRadiusBoundsPx:
    def test_typical(self) -> None:
        min_r, max_r = _radius_bounds_px(13.0, 0.3, mm_per_px=1 / 17.0)
        # target=13, tol=0.3, ppm=17 -> min=(12.7/2)*17=107.95 -> 107
        # max=(13.3/2)*17=113.05 -> 113
        assert min_r == 107
        assert max_r == 113

    def test_never_zero(self) -> None:
        min_r, max_r = _radius_bounds_px(0.01, 0.001, mm_per_px=1.0)
        assert min_r >= 1
        assert max_r > min_r

    def test_invalid_mm_per_px(self) -> None:
        with pytest.raises(ValueError, match="mm_per_px"):
            _radius_bounds_px(13.0, 0.3, mm_per_px=0.0)


class TestDetectCircleInContour:
    def test_detects_matching_circle(self) -> None:
        gray = np.full((300, 300), 200, dtype=np.uint8)
        cv2.circle(gray, (150, 150), 50, 40, -1)  # dark filled circle

        binary = np.zeros_like(gray)
        cv2.circle(binary, (150, 150), 50, 255, -1)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # target diameter ≈ 100 px at mm_per_px = 0.1  ->  10 mm
        mm_per_px = 0.1
        circle = detect_circle_in_contour(
            gray,
            contours[0],
            mm_per_px=mm_per_px,
            target_diameter_mm=10.0,
            radius_tolerance_mm=1.0,
            param2=15,
        )
        assert circle is not None
        assert abs(circle.cx - 150) <= 5
        assert abs(circle.cy - 150) <= 5
        assert abs(circle.radius_px - 50) <= 5

    def test_rejects_wrong_size(self) -> None:
        gray = np.full((300, 300), 200, dtype=np.uint8)
        cv2.circle(gray, (150, 150), 50, 40, -1)

        binary = np.zeros_like(gray)
        cv2.circle(binary, (150, 150), 50, 255, -1)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Expect radius ~200px but actual is ~50px -> reject
        circle = detect_circle_in_contour(
            gray,
            contours[0],
            mm_per_px=0.1,
            target_diameter_mm=40.0,
            radius_tolerance_mm=0.5,
        )
        assert circle is None


class TestDetectCircle:
    def test_end_to_end(self) -> None:
        # Bright plate with a dark hole
        gray = np.full((400, 400), 200, dtype=np.uint8)
        cv2.circle(gray, (200, 200), 40, 30, -1)

        binary = np.zeros_like(gray)
        cv2.circle(binary, (200, 200), 40, 255, -1)

        circle = detect_circle(
            gray,
            binary,
            mm_per_px=0.1,
            target_diameter_mm=8.0,  # 40px radius -> 80px diameter -> 8mm
            radius_tolerance_mm=0.5,
            param2=15,
        )
        assert circle is not None
        assert 35 <= circle.radius_px <= 45

    def test_prefers_largest_contour(self) -> None:
        # Two bright regions, only the large one contains the target circle
        gray = np.full((400, 400), 200, dtype=np.uint8)
        cv2.circle(gray, (300, 300), 40, 30, -1)  # inside large region

        binary = np.zeros_like(gray)
        cv2.circle(binary, (300, 300), 80, 255, -1)  # large contour
        cv2.rectangle(binary, (20, 20), (40, 40), 255, -1)  # small contour

        circle = detect_circle(
            gray,
            binary,
            mm_per_px=0.1,
            target_diameter_mm=8.0,
            radius_tolerance_mm=0.5,
            param2=15,
        )
        assert circle is not None
        assert 280 <= circle.cx <= 320

    def test_no_circle_returns_none(self) -> None:
        gray = np.full((200, 200), 150, dtype=np.uint8)
        binary = np.zeros_like(gray)
        cv2.rectangle(binary, (60, 60), (140, 140), 255, -1)

        circle = detect_circle(
            gray,
            binary,
            mm_per_px=0.1,
            target_diameter_mm=8.0,
            radius_tolerance_mm=0.3,
        )
        assert circle is None
