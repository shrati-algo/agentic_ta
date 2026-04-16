"""Tests for tad.measurement.preprocessing."""

from __future__ import annotations

import cv2
import numpy as np

from tad.measurement.preprocessing import clahe, gaussian_blur


class TestCLAHE:
    def test_output_same_shape(self) -> None:
        gray = np.random.default_rng(1).integers(50, 200, (100, 120), dtype=np.uint8)
        result = clahe(gray)
        assert result.shape == gray.shape
        assert result.dtype == np.uint8

    def test_improves_contrast(self) -> None:
        # Low-contrast image: all values in [100, 110]
        gray = np.random.default_rng(2).integers(100, 110, (200, 200), dtype=np.uint8)
        result = clahe(gray, clip_limit=2.0)
        # After CLAHE, the range should be wider
        assert int(result.max()) - int(result.min()) > int(gray.max()) - int(gray.min())


class TestGaussianBlur:
    def test_output_same_shape(self) -> None:
        img = np.random.default_rng(3).integers(0, 255, (100, 120, 3), dtype=np.uint8)
        result = gaussian_blur(img, kernel=5)
        assert result.shape == img.shape

    def test_reduces_noise(self) -> None:
        # Noisy grayscale image
        gray = np.random.default_rng(4).integers(0, 255, (200, 200), dtype=np.uint8)
        blurred = gaussian_blur(gray, kernel=5)
        # Laplacian variance should be lower after blurring
        original_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        blurred_var = cv2.Laplacian(blurred, cv2.CV_64F).var()
        assert blurred_var < original_var
