"""Edge detection with adaptive Canny thresholds."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def adaptive_canny(
    gray: np.ndarray[Any, Any],
    lower_ratio: float = 0.66,
    upper_ratio: float = 1.33,
) -> np.ndarray[Any, Any]:
    """Run Canny edge detection with thresholds derived from the image median.

    Parameters
    ----------
    gray:
        Single-channel grayscale image (uint8).
    lower_ratio:
        Multiplier for the lower threshold (relative to median).
    upper_ratio:
        Multiplier for the upper threshold (relative to median).

    Returns
    -------
    np.ndarray
        Binary edge map (uint8, values 0 or 255).
    """
    v = float(np.median(gray))
    lower = int(max(0, lower_ratio * v))
    upper = int(min(255, upper_ratio * v))
    return cv2.Canny(gray, lower, upper)
