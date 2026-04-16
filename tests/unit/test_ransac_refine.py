"""Tests for tad.measurement.ransac_refine."""

from __future__ import annotations

import cv2
import numpy as np

from tad.measurement.models import InnerCircle
from tad.measurement.ransac_refine import fit_circle_3pt, refine_subpixel


class TestFitCircle3pt:
    def test_known_circle(self) -> None:
        # Three points on a circle centred at (100, 100) with radius 50
        xs = np.array([150.0, 100.0, 50.0])
        ys = np.array([100.0, 150.0, 100.0])
        result = fit_circle_3pt(xs, ys)
        assert result is not None
        assert abs(result.cx - 100) <= 1
        assert abs(result.cy - 100) <= 1
        assert abs(result.radius_px - 50.0) < 0.1

    def test_collinear_returns_none(self) -> None:
        xs = np.array([0.0, 1.0, 2.0])
        ys = np.array([0.0, 1.0, 2.0])
        result = fit_circle_3pt(xs, ys)
        assert result is None

    def test_different_circle(self) -> None:
        # Points on a circle with r=30, centre (50, 60)
        import math

        angles = [0, 2 * math.pi / 3, 4 * math.pi / 3]
        r = 30.0
        cx, cy = 50.0, 60.0
        xs = np.array([cx + r * math.cos(a) for a in angles])
        ys = np.array([cy + r * math.sin(a) for a in angles])
        result = fit_circle_3pt(xs, ys)
        assert result is not None
        assert abs(result.radius_px - 30.0) < 0.5


class TestRefineSubpixel:
    def test_refines_close_to_seed(self) -> None:
        # Draw a circle and use its edges for RANSAC
        img = np.zeros((300, 300), dtype=np.uint8)
        cv2.circle(img, (150, 150), 60, 255, 2)
        edges = cv2.Canny(img, 50, 150)

        seed = InnerCircle(cx=150, cy=150, radius_px=60.0)
        refined, residual = refine_subpixel(edges, seed, iterations=100)

        assert abs(refined.cx - 150) <= 3
        assert abs(refined.cy - 150) <= 3
        assert abs(refined.radius_px - 60.0) < 3.0
        assert residual <= 1.0

    def test_deterministic_with_same_seed(self) -> None:
        img = np.zeros((300, 300), dtype=np.uint8)
        cv2.circle(img, (150, 150), 60, 255, 2)
        edges = cv2.Canny(img, 50, 150)
        seed = InnerCircle(cx=150, cy=150, radius_px=60.0)

        r1, res1 = refine_subpixel(edges, seed, rng_seed=42)
        r2, res2 = refine_subpixel(edges, seed, rng_seed=42)

        assert r1.cx == r2.cx
        assert r1.cy == r2.cy
        assert r1.radius_px == r2.radius_px
        assert res1 == res2

    def test_returns_seed_on_sparse_edges(self) -> None:
        # Very few edge points -> should return the seed unchanged
        edges = np.zeros((300, 300), dtype=np.uint8)
        edges[150, 150] = 255
        edges[151, 151] = 255

        seed = InnerCircle(cx=150, cy=150, radius_px=60.0)
        refined, residual = refine_subpixel(edges, seed)

        assert refined.cx == seed.cx
        assert refined.cy == seed.cy
        assert refined.radius_px == seed.radius_px
        assert residual == 1.0
