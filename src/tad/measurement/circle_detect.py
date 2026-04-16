"""Hough circle detection and innermost-circle selection."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from tad.measurement.models import InnerCircle


def hough_circles(
    blurred_gray: np.ndarray[Any, Any],
    *,
    dp: float = 1.2,
    min_dist: int = 40,
    param1: int = 100,
    param2: int = 30,
    min_radius: int = 40,
    max_radius: int = 160,
) -> np.ndarray[Any, Any] | None:
    """Detect circles using the Hough transform.

    Parameters
    ----------
    blurred_gray:
        Pre-processed single-channel image (uint8, already blurred).

    Returns
    -------
    np.ndarray | None
        Array of shape ``(1, N, 3)`` with ``(x, y, radius)`` per circle,
        or ``None`` if no circles are detected.
    """
    circles = cv2.HoughCircles(
        blurred_gray,
        cv2.HOUGH_GRADIENT,
        dp=dp,
        minDist=min_dist,
        param1=param1,
        param2=param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    return circles


def pick_innermost(
    circles: np.ndarray[Any, Any],
    image_shape: tuple[int, ...],
    inner_fraction: float = 0.7,
) -> InnerCircle | None:
    """Select the smallest circle whose centre is inside the central region.

    The central region is defined by ``inner_fraction`` of the image
    dimensions around the image centre.  This avoids picking unrelated
    holes near the edges of the frame.

    Parameters
    ----------
    circles:
        Output of :func:`hough_circles` — shape ``(1, N, 3)``.
    image_shape:
        ``(height, width, ...)`` from ``image.shape``.
    inner_fraction:
        Fraction of image dimensions defining the central region (0-1).

    Returns
    -------
    InnerCircle | None
        The innermost circle, or ``None`` if no candidate falls in the
        central region.
    """
    h, w = image_shape[:2]
    cx_c, cy_c = w / 2.0, h / 2.0
    half_w = (w * inner_fraction) / 2.0
    half_h = (h * inner_fraction) / 2.0

    # Sort ascending by radius
    ordered = sorted(circles[0], key=lambda c: float(c[2]))
    for circ in ordered:
        x, y, r = float(circ[0]), float(circ[1]), float(circ[2])
        if abs(x - cx_c) <= half_w and abs(y - cy_c) <= half_h:
            return InnerCircle(
                cx=int(round(x)),
                cy=int(round(y)),
                radius_px=r,
                peak=1.0,  # HoughCircles doesn't expose accumulator; normalise to 1
            )
    return None
