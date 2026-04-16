"""Adaptive thresholding and morphological clean-up.

Replaces the Canny edge detector in the pipeline.  Under the bright,
uneven industrial lighting on the assembly line, a global threshold
fails (half the image is saturated, half is in shadow).  An adaptive
Gaussian threshold computes a local cut-off per pixel which cleanly
separates the dark hole interiors from the bright plate surface.

The morphological close step fills small gaps in the thresholded
binary so that each hole becomes a single closed contour for
downstream contour extraction.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def adaptive_threshold(
    blurred_gray: np.ndarray[Any, Any],
    *,
    block_size: int = 51,
    c: int = 10,
) -> np.ndarray[Any, Any]:
    """Adaptive Gaussian threshold, inverted so holes become foreground.

    Parameters
    ----------
    blurred_gray:
        Single-channel grayscale image after Gaussian blur.
    block_size:
        Neighbourhood size (odd integer) for the local mean.  Larger
        values average over a bigger region, so very slow lighting
        gradients are absorbed.  51 is a good default at 3072x2048.
    c:
        Constant subtracted from the local mean.  Higher values make
        the threshold stricter (more pixels stay black).

    Returns
    -------
    np.ndarray
        Binary mask (uint8, values 0 or 255) where holes/dark regions
        are 255 and the plate background is 0.
    """
    if block_size % 2 == 0:
        msg = f"block_size must be odd, got {block_size}"
        raise ValueError(msg)

    return cv2.adaptiveThreshold(
        blurred_gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        block_size,
        c,
    )


def morph_close(
    binary: np.ndarray[Any, Any],
    *,
    kernel_size: int = 3,
    iterations: int = 1,
) -> np.ndarray[Any, Any]:
    """Morphological close: dilate then erode.

    Fills small holes in the foreground and bridges narrow gaps.
    Conservative defaults (3x3, 1 iteration) are enough to stitch
    adjacent edge pixels without merging distinct holes.

    Parameters
    ----------
    binary:
        Binary mask (uint8, 0 or 255).
    kernel_size:
        Side length of the square structuring element.
    iterations:
        Number of close iterations.

    Returns
    -------
    np.ndarray
        Cleaned binary mask, same shape and dtype as the input.
    """
    kernel = np.ones((kernel_size, kernel_size), np.uint8)
    return cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=iterations)
