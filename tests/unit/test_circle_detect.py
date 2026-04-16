"""Tests for tad.measurement.circle_detect."""

from __future__ import annotations

import cv2
import numpy as np

from tad.measurement.circle_detect import hough_circles, pick_innermost
from tad.measurement.models import InnerCircle


def _make_circle_image(
    w: int = 400,
    h: int = 400,
    cx: int = 200,
    cy: int = 200,
    radius: int = 80,
    *,
    add_outer: bool = False,
) -> np.ndarray:  # type: ignore[type-arg]
    """Create a synthetic grayscale image with a drawn circle."""
    img = np.full((h, w), 128, dtype=np.uint8)
    cv2.circle(img, (cx, cy), radius, 255, 2)
    if add_outer:
        cv2.circle(img, (cx, cy), radius + 40, 200, 2)
    return img


class TestHoughCircles:
    def test_detects_circle(self) -> None:
        img = _make_circle_image()
        blurred = cv2.GaussianBlur(img, (5, 5), 0)
        circles = hough_circles(
            blurred,
            dp=1.2,
            min_dist=40,
            param1=100,
            param2=20,
            min_radius=50,
            max_radius=150,
        )
        assert circles is not None
        assert len(circles[0]) >= 1

    def test_returns_none_on_blank(self) -> None:
        img = np.full((200, 200), 128, dtype=np.uint8)
        circles = hough_circles(img, param2=100, min_radius=20, max_radius=80)
        assert circles is None

    def test_detected_radius_reasonable(self) -> None:
        radius = 80
        img = _make_circle_image(radius=radius)
        blurred = cv2.GaussianBlur(img, (5, 5), 0)
        circles = hough_circles(
            blurred,
            dp=1.2,
            min_dist=40,
            param1=100,
            param2=20,
            min_radius=50,
            max_radius=150,
        )
        assert circles is not None
        detected_r = float(circles[0][0][2])
        assert abs(detected_r - radius) < 15


class TestPickInnermost:
    def test_picks_smallest_in_center(self) -> None:
        # Two circles: one small (r=50) and one large (r=100), both centred
        circles = np.array([[[200, 200, 50], [200, 200, 100]]], dtype=np.float32)
        result = pick_innermost(circles, (400, 400, 3), inner_fraction=0.7)
        assert result is not None
        assert result.radius_px == 50.0

    def test_ignores_circle_outside_center(self) -> None:
        # One circle at (10, 10) — outside centre region
        circles = np.array([[[10, 10, 50]]], dtype=np.float32)
        result = pick_innermost(circles, (400, 400, 3), inner_fraction=0.3)
        assert result is None

    def test_skips_outer_picks_inner(self) -> None:
        # Outer circle at edge, inner circle at centre
        circles = np.array(
            [
                [[10, 10, 30], [200, 200, 60]],
            ],
            dtype=np.float32,
        )
        result = pick_innermost(circles, (400, 400, 3), inner_fraction=0.5)
        assert result is not None
        assert result.radius_px == 60.0

    def test_returns_none_on_empty(self) -> None:
        circles = np.array([[[10, 10, 50]]], dtype=np.float32)
        result = pick_innermost(circles, (400, 400, 3), inner_fraction=0.01)
        assert result is None

    def test_result_is_inner_circle(self) -> None:
        circles = np.array([[[200, 200, 50]]], dtype=np.float32)
        result = pick_innermost(circles, (400, 400, 3))
        assert isinstance(result, InnerCircle)
        assert result.cx == 200
        assert result.cy == 200
