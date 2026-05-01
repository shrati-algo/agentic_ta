"""Validate an image against the Image Contract (TRD Section 5.1).

Every image must pass all quality gates before entering the measurement
pipeline.  The validator returns both the decoded image (if valid) and
a structured result so the caller can persist error details.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import cv2
import numpy as np

# ---------------------------------------------------------------------------
# Defaults from TRD Section 5.1
# ---------------------------------------------------------------------------
MIN_RESOLUTION = (2048, 1536)
MAX_RESOLUTION = (4096, 3072)
MAX_FILE_SIZE = 15 * 1024 * 1024  # 15 MB
BLUR_LAPLACIAN_MIN = 100.0
EXPOSURE_MIN = 40.0
EXPOSURE_MAX = 220.0


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of image validation."""

    ok: bool
    error_code: str | None = None
    message: str | None = None
    meta: dict[str, object] = field(default_factory=dict)


def validate_image(
    image_bytes: bytes,
    *,
    min_resolution: tuple[int, int] = MIN_RESOLUTION,
    max_resolution: tuple[int, int] = MAX_RESOLUTION,
    max_file_size: int = MAX_FILE_SIZE,
    blur_min: float = BLUR_LAPLACIAN_MIN,
    exposure_range: tuple[float, float] = (EXPOSURE_MIN, EXPOSURE_MAX),
) -> tuple[np.ndarray[Any, Any] | None, ValidationResult]:
    """Validate raw image bytes against the Image Contract.

    Parameters
    ----------
    image_bytes:
        Raw file content (JPEG or PNG).
    min_resolution, max_resolution:
        Acceptable width x height bounds.
    max_file_size:
        Maximum file size in bytes.
    blur_min:
        Minimum Laplacian-variance blur metric.
    exposure_range:
        Acceptable (min, max) for mean pixel intensity.

    Returns
    -------
    tuple[np.ndarray | None, ValidationResult]
        The decoded BGR image (or ``None`` on failure) and the result.
    """
    meta: dict[str, object] = {}

    # ---- file size --------------------------------------------------------
    meta["file_size"] = len(image_bytes)
    if len(image_bytes) == 0:
        return None, ValidationResult(
            ok=False,
            error_code="ERR_IMAGE_QUALITY",
            message="empty file",
            meta=meta,
        )
    if len(image_bytes) > max_file_size:
        return None, ValidationResult(
            ok=False,
            error_code="ERR_IMAGE_QUALITY",
            message=f"file exceeds {max_file_size} bytes",
            meta=meta,
        )

    # ---- decode -----------------------------------------------------------
    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if image is None:
        return None, ValidationResult(
            ok=False,
            error_code="ERR_IMAGE_QUALITY",
            message="failed to decode image (corrupt or unsupported format)",
            meta=meta,
        )

    h, w = image.shape[:2]
    channels = image.shape[2] if image.ndim == 3 else 1
    meta["width"] = w
    meta["height"] = h
    meta["channels"] = channels

    # ---- colour space (must be 3-channel RGB/BGR) -------------------------
    if channels != 3:
        return None, ValidationResult(
            ok=False,
            error_code="ERR_IMAGE_QUALITY",
            message=f"expected 3 channels, got {channels}",
            meta=meta,
        )

    # ---- resolution -------------------------------------------------------
    min_w, min_h = min_resolution
    max_w, max_h = max_resolution
    if w < min_w or h < min_h:
        return None, ValidationResult(
            ok=False,
            error_code="ERR_IMAGE_QUALITY",
            message=f"resolution {w}x{h} below minimum {min_w}x{min_h}",
            meta=meta,
        )
    if w > max_w or h > max_h:
        return None, ValidationResult(
            ok=False,
            error_code="ERR_IMAGE_QUALITY",
            message=f"resolution {w}x{h} exceeds maximum {max_w}x{max_h}",
            meta=meta,
        )

    # ---- blur (Laplacian variance) ----------------------------------------
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    meta["blur_laplacian_var"] = round(blur_var, 2)
    if blur_var < blur_min:
        return None, ValidationResult(
            ok=False,
            error_code="ERR_IMAGE_QUALITY",
            message=f"image too blurry (Laplacian variance {blur_var:.1f} < {blur_min})",
            meta=meta,
        )

    # ---- exposure (mean pixel intensity) ----------------------------------
    exposure = float(gray.mean())
    meta["exposure_mean"] = round(exposure, 2)
    exp_lo, exp_hi = exposure_range
    if exposure < exp_lo or exposure > exp_hi:
        return None, ValidationResult(
            ok=False,
            error_code="ERR_IMAGE_QUALITY",
            message=f"exposure {exposure:.1f} outside [{exp_lo}, {exp_hi}]",
            meta=meta,
        )

    # ---- all gates passed -------------------------------------------------
    return image, ValidationResult(ok=True, meta=meta)
