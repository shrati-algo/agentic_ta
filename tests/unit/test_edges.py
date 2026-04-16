"""Tests for tad.measurement.edges."""

from __future__ import annotations

import cv2
import numpy as np

from tad.measurement.edges import adaptive_canny


class TestAdaptiveCanny:
    def test_output_binary(self) -> None:
        gray = np.random.default_rng(10).integers(50, 200, (100, 120), dtype=np.uint8)
        edges = adaptive_canny(gray)
        assert edges.dtype == np.uint8
        # Canny output is binary: only 0 and 255
        unique = set(np.unique(edges))
        assert unique <= {0, 255}

    def test_detects_edges_on_circle(self) -> None:
        # Draw a white circle on black background -> should have edges
        img = np.zeros((200, 200), dtype=np.uint8)
        cv2.circle(img, (100, 100), 50, 255, 2)
        edges = adaptive_canny(img, lower_ratio=0.3, upper_ratio=0.7)
        assert np.sum(edges > 0) > 0

    def test_blank_image_no_edges(self) -> None:
        # Uniform image -> no edges
        img = np.full((100, 100), 128, dtype=np.uint8)
        edges = adaptive_canny(img)
        assert np.sum(edges > 0) == 0

    def test_output_same_shape(self) -> None:
        gray = np.random.default_rng(11).integers(0, 255, (150, 200), dtype=np.uint8)
        edges = adaptive_canny(gray)
        assert edges.shape == gray.shape
