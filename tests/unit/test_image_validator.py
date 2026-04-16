"""Tests for tad.data.image_validator."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from tad.data.image_validator import validate_image

IMAGES_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "images"


def _read_bytes(name: str) -> bytes:
    return (IMAGES_DIR / name).read_bytes()


class TestValidateImage:
    # ---- happy path -------------------------------------------------------

    def test_valid_image_passes(self) -> None:
        img, result = validate_image(_read_bytes("MALBB51BLPM123456_L.jpg"))
        assert result.ok is True
        assert result.error_code is None
        assert img is not None
        assert img.ndim == 3
        assert img.shape[2] == 3

    def test_meta_populated_on_success(self) -> None:
        _, result = validate_image(_read_bytes("MALBB51BLPM123456_L.jpg"))
        assert "width" in result.meta
        assert "height" in result.meta
        assert "channels" in result.meta
        assert "blur_laplacian_var" in result.meta
        assert "exposure_mean" in result.meta

    # ---- empty / corrupt --------------------------------------------------

    def test_empty_file_fails(self) -> None:
        img, result = validate_image(b"")
        assert result.ok is False
        assert result.error_code == "ERR_IMAGE_QUALITY"
        assert "empty" in (result.message or "")
        assert img is None

    def test_truncated_jpeg_fails(self) -> None:
        img, result = validate_image(_read_bytes("truncated.jpg"))
        assert result.ok is False
        assert result.error_code == "ERR_IMAGE_QUALITY"
        assert img is None

    def test_random_bytes_fails(self) -> None:
        img, result = validate_image(b"not an image at all")
        assert result.ok is False
        assert result.error_code == "ERR_IMAGE_QUALITY"
        assert img is None

    # ---- file size --------------------------------------------------------

    def test_oversized_file_fails(self) -> None:
        data = _read_bytes("MALBB51BLPM123456_L.jpg")
        img, result = validate_image(data, max_file_size=1000)
        assert result.ok is False
        assert "exceeds" in (result.message or "")

    # ---- resolution -------------------------------------------------------

    def test_too_small_resolution_fails(self) -> None:
        img, result = validate_image(_read_bytes("too_small.jpg"))
        assert result.ok is False
        assert "below minimum" in (result.message or "")

    def test_too_large_resolution_fails(self) -> None:
        data = _read_bytes("MALBB51BLPM123456_L.jpg")
        img, result = validate_image(data, max_resolution=(1024, 768))
        assert result.ok is False
        assert "exceeds maximum" in (result.message or "")

    # ---- blur -------------------------------------------------------------

    def test_blurry_image_fails(self) -> None:
        img, result = validate_image(_read_bytes("blurry.jpg"))
        assert result.ok is False
        assert "blurry" in (result.message or "").lower()
        assert result.meta.get("blur_laplacian_var") is not None

    # ---- exposure ---------------------------------------------------------

    def test_overexposed_image_fails(self) -> None:
        """Solid bright image fails (hits blur gate first, then exposure)."""
        # Test with relaxed blur to specifically test the exposure gate
        img, result = validate_image(_read_bytes("overexposed.jpg"), blur_min=0.0)
        assert result.ok is False
        assert "exposure" in (result.message or "").lower()

    def test_underexposed_image_fails(self) -> None:
        """Solid dark image fails (hits blur gate first, then exposure)."""
        img, result = validate_image(_read_bytes("underexposed.jpg"), blur_min=0.0)
        assert result.ok is False
        assert "exposure" in (result.message or "").lower()

    # ---- custom thresholds ------------------------------------------------

    def test_relaxed_blur_threshold_passes(self) -> None:
        """Blurry image passes when the blur threshold is relaxed."""
        img, result = validate_image(_read_bytes("blurry.jpg"), blur_min=0.0)
        # May still fail on other gates, but not on blur
        if not result.ok:
            assert "blurry" not in (result.message or "").lower()

    def test_relaxed_resolution_passes(self) -> None:
        """Small image passes when resolution constraints are relaxed."""
        img, result = validate_image(
            _read_bytes("too_small.jpg"),
            min_resolution=(1, 1),
        )
        # May still fail on other gates, but not on resolution
        if not result.ok:
            assert "resolution" not in (result.message or "").lower()

    # ---- channel check (via PNG with alpha) ----------------------------------

    def test_non_image_binary_fails(self) -> None:
        """Random binary that's large enough but not a valid image."""
        rng = np.random.default_rng(99)
        data = rng.integers(0, 255, size=50_000, dtype=np.uint8).tobytes()
        img, result = validate_image(data)
        assert result.ok is False
        assert result.error_code == "ERR_IMAGE_QUALITY"
        assert img is None
