"""Tests for tad.processing.threshold."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from tad.processing.threshold import adaptive_threshold, morph_close


class TestAdaptiveThreshold:
    def test_output_binary(self) -> None:
        gray = np.random.default_rng(1).integers(0, 255, (200, 200), dtype=np.uint8)
        result = adaptive_threshold(gray, block_size=51, c=10)
        assert result.dtype == np.uint8
        assert set(np.unique(result)) <= {0, 255}
        assert result.shape == gray.shape

    def test_odd_block_size_required(self) -> None:
        gray = np.full((100, 100), 128, dtype=np.uint8)
        with pytest.raises(ValueError, match="block_size must be odd"):
            adaptive_threshold(gray, block_size=50, c=10)

    def test_detects_dark_hole_on_bright_background(self) -> None:
        """A dark circle on a bright plate becomes foreground (255).

        The hole radius must be smaller than ``block_size / 2`` so that
        each local window averages plate+hole pixels — otherwise the
        local mean inside a large uniform hole is itself dark and the
        threshold correctly concludes 'nothing locally abnormal here'.
        """
        img = np.full((300, 300), 220, dtype=np.uint8)  # bright plate
        cv2.circle(img, (150, 150), 10, 30, -1)  # small dark hole

        binary = adaptive_threshold(img, block_size=51, c=10)

        # Inside the small hole the pixel should be flagged as foreground
        assert binary[150, 150] == 255
        # Far from the hole on the bright plate should be background
        assert binary[10, 10] == 0

    def test_larger_c_removes_more(self) -> None:
        """Increasing c makes the threshold stricter (less foreground)."""
        img = np.random.default_rng(2).integers(50, 200, (200, 200), dtype=np.uint8)
        b_low = adaptive_threshold(img, block_size=51, c=2)
        b_high = adaptive_threshold(img, block_size=51, c=30)
        assert int(np.sum(b_high > 0)) <= int(np.sum(b_low > 0))


class TestMorphClose:
    def test_output_same_shape(self) -> None:
        binary = np.random.default_rng(3).integers(0, 2, (100, 100), dtype=np.uint8) * 255
        result = morph_close(binary)
        assert result.shape == binary.shape
        assert result.dtype == np.uint8

    def test_fills_small_gap(self) -> None:
        """A thin gap in a bright blob should be closed."""
        binary = np.zeros((100, 100), dtype=np.uint8)
        cv2.rectangle(binary, (20, 20), (80, 80), 255, -1)
        # Carve a 2-pixel gap
        binary[40:42, 20:80] = 0

        closed = morph_close(binary, kernel_size=3, iterations=2)
        # The gap should be filled after close
        assert int(np.sum(closed[40:42, 20:80] > 0)) > int(np.sum(binary[40:42, 20:80] > 0))

    def test_preserves_binary_values(self) -> None:
        binary = np.random.default_rng(4).integers(0, 2, (50, 50), dtype=np.uint8) * 255
        result = morph_close(binary)
        assert set(np.unique(result)) <= {0, 255}
