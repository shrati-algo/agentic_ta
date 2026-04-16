"""Image preprocessing: CLAHE contrast normalisation and Gaussian blur."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def clahe(
    gray: np.ndarray[Any, Any],
    clip_limit: float = 2.0,
    tile_grid_size: tuple[int, int] = (8, 8),
) -> np.ndarray[Any, Any]:
    """Apply Contrast-Limited Adaptive Histogram Equalisation.

    Parameters
    ----------
    gray:
        Single-channel grayscale image (uint8).
    clip_limit:
        Threshold for contrast limiting.
    tile_grid_size:
        Size of the grid for histogram equalisation.

    Returns
    -------
    np.ndarray
        Contrast-normalised grayscale image.
    """
    cl = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_grid_size)
    return cl.apply(gray)


def gaussian_blur(
    image: np.ndarray[Any, Any],
    kernel: int = 5,
) -> np.ndarray[Any, Any]:
    """Apply Gaussian blur to suppress sensor noise.

    Parameters
    ----------
    image:
        Input image (any number of channels).
    kernel:
        Kernel size (must be odd).

    Returns
    -------
    np.ndarray
        Blurred image.
    """
    return cv2.GaussianBlur(image, (kernel, kernel), 0)
