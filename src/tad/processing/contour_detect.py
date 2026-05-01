"""Contour-driven circle detection.

Replaces the pick-innermost-then-RANSAC approach.  The binary mask from
:mod:`tad.processing.threshold` is decomposed into external contours.
We iterate the contours from largest to smallest and, for each, build
a mask and run a target-constrained :func:`cv2.HoughCircles`.  The
first contour that yields a circle whose radius lies within
``target_diameter_mm ± radius_tolerance_mm`` wins.

This design solves two problems that broke the RANSAC approach on real
images:

1. **Noise rejection.**  The target-radius constraint throws away every
   phantom circle whose size does not match the part being measured.
2. **Isolation.**  Running Hough on a contour-masked image prevents the
   vote accumulator from being swamped by unrelated edges elsewhere in
   the frame.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np

from tad.processing.models import InnerCircle


def find_candidate_contours(
    binary_mask: np.ndarray[Any, Any],
    *,
    min_area: float = 50.0,
) -> list[np.ndarray[Any, Any]]:
    """Extract external contours, sorted largest-area first.

    Parameters
    ----------
    binary_mask:
        Binary image (uint8, 0 or 255) from adaptive threshold + morph.
    min_area:
        Contours below this pixel area are discarded as noise.

    Returns
    -------
    list[np.ndarray]
        Contours sorted by area descending, each as an ``(N, 1, 2)``
        integer array (OpenCV convention).
    """
    contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filtered = [c for c in contours if cv2.contourArea(c) >= min_area]
    return sorted(filtered, key=cv2.contourArea, reverse=True)


def _radius_bounds_px(
    target_diameter_mm: float,
    radius_tolerance_mm: float,
    mm_per_px: float,
) -> tuple[int, int]:
    """Convert a diameter window in mm to a (min_r, max_r) px pair."""
    if mm_per_px <= 0:
        msg = f"mm_per_px must be positive, got {mm_per_px}"
        raise ValueError(msg)
    ppm = 1.0 / mm_per_px
    min_r = int(max(1.0, (target_diameter_mm - radius_tolerance_mm) / 2.0 * ppm))
    max_r = int((target_diameter_mm + radius_tolerance_mm) / 2.0 * ppm)
    if max_r <= min_r:
        max_r = min_r + 1
    return min_r, max_r


def detect_circle_in_contour(
    gray: np.ndarray[Any, Any],
    contour: np.ndarray[Any, Any],
    *,
    mm_per_px: float,
    target_diameter_mm: float,
    radius_tolerance_mm: float = 0.3,
    dp: float = 1.2,
    min_dist: int = 10,
    param1: int = 50,
    param2: int = 20,
) -> InnerCircle | None:
    """Run Hough on the region covered by *contour* and return the first
    circle whose radius matches the target band.
    """
    min_radius, max_radius = _radius_bounds_px(target_diameter_mm, radius_tolerance_mm, mm_per_px)

    mask = np.zeros_like(gray)
    cv2.drawContours(mask, [contour], -1, 255, thickness=cv2.FILLED)
    masked_gray = cv2.bitwise_and(gray, gray, mask=mask)

    circles = cv2.HoughCircles(
        masked_gray,
        cv2.HOUGH_GRADIENT,
        dp=dp,
        minDist=min_dist,
        param1=param1,
        param2=param2,
        minRadius=min_radius,
        maxRadius=max_radius,
    )
    if circles is None or len(circles[0]) == 0:
        return None

    x, y, r = (float(v) for v in circles[0][0])
    return InnerCircle(
        cx=int(round(x)),
        cy=int(round(y)),
        radius_px=r,
        peak=1.0,
    )


def detect_circle(
    gray: np.ndarray[Any, Any],
    binary_mask: np.ndarray[Any, Any],
    *,
    mm_per_px: float,
    target_diameter_mm: float,
    radius_tolerance_mm: float = 0.3,
    min_contour_area: float = 50.0,
    dp: float = 1.2,
    min_dist: int = 10,
    param1: int = 50,
    param2: int = 20,
) -> InnerCircle | None:
    """Full contour-based circle search.

    Iterates contours largest-first and returns the first contour's
    matching circle, or ``None`` if no candidate in any contour meets
    the target radius band.
    """
    for contour in find_candidate_contours(binary_mask, min_area=min_contour_area):
        circle = detect_circle_in_contour(
            gray,
            contour,
            mm_per_px=mm_per_px,
            target_diameter_mm=target_diameter_mm,
            radius_tolerance_mm=radius_tolerance_mm,
            dp=dp,
            min_dist=min_dist,
            param1=param1,
            param2=param2,
        )
        if circle is not None:
            return circle
    return None
