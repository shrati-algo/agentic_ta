"""RANSAC circle fitting for sub-pixel accuracy refinement.

Given an initial circle estimate (from Hough) and a Canny edge map,
refine the circle parameters to sub-pixel accuracy using RANSAC on
nearby edge points.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from tad.measurement.models import InnerCircle

# Minimum edge points needed for a meaningful RANSAC fit
_MIN_EDGE_POINTS = 20

# Annulus width (px) around the seed circle to select edge candidates
_ANNULUS_WIDTH = 5.0


def fit_circle_3pt(
    xs: np.ndarray[Any, Any],
    ys: np.ndarray[Any, Any],
) -> InnerCircle | None:
    """Fit a circle through exactly 3 points.

    Uses the algebraic solution via the determinant method.

    Returns
    -------
    InnerCircle | None
        The fitted circle, or ``None`` if the points are collinear.
    """
    x1, x2, x3 = float(xs[0]), float(xs[1]), float(xs[2])
    y1, y2, y3 = float(ys[0]), float(ys[1]), float(ys[2])

    ax = x1 - x2
    ay = y1 - y2
    bx = x1 - x3
    by = y1 - y3

    d = 2.0 * (ax * by - ay * bx)
    if abs(d) < 1e-10:
        return None  # collinear

    a_sq = x1 * x1 + y1 * y1
    b_sq = x2 * x2 + y2 * y2
    c_sq = x3 * x3 + y3 * y3

    cx = ((a_sq - b_sq) * by - (a_sq - c_sq) * ay) / d
    cy = ((a_sq - c_sq) * ax - (a_sq - b_sq) * bx) / d
    r = float(np.sqrt((x1 - cx) ** 2 + (y1 - cy) ** 2))

    if r <= 0:
        return None

    return InnerCircle(cx=int(round(cx)), cy=int(round(cy)), radius_px=r)


def refine_subpixel(
    edges: np.ndarray[Any, Any],
    seed: InnerCircle,
    *,
    iterations: int = 200,
    inlier_threshold_px: float = 1.0,
    rng_seed: int = 42,
) -> tuple[InnerCircle, float]:
    """Refine a circle estimate using RANSAC on nearby edge points.

    Parameters
    ----------
    edges:
        Binary edge map (Canny output).
    seed:
        Initial circle estimate from Hough detection.
    iterations:
        Number of RANSAC iterations.
    inlier_threshold_px:
        Maximum residual (px) for an edge point to count as an inlier.
    rng_seed:
        Fixed seed for the random number generator (determinism).

    Returns
    -------
    tuple[InnerCircle, float]
        The refined circle and the mean inlier residual (lower is better,
        capped at 1.0).
    """
    ys, xs = np.where(edges > 0)

    # Keep only edge points within an annulus around the seed circle
    r = seed.radius_px
    d = np.sqrt((xs - seed.cx) ** 2 + (ys - seed.cy) ** 2)
    mask = np.abs(d - r) <= _ANNULUS_WIDTH
    xs, ys = xs[mask], ys[mask]

    if len(xs) < _MIN_EDGE_POINTS:
        return seed, 1.0

    rng = np.random.default_rng(rng_seed)
    best_inliers = 0
    best = seed
    best_residual = 1.0

    for _ in range(iterations):
        idx = rng.choice(len(xs), size=3, replace=False)
        cand = fit_circle_3pt(xs[idx], ys[idx])
        if cand is None:
            continue

        resid = np.abs(np.sqrt((xs - cand.cx) ** 2 + (ys - cand.cy) ** 2) - cand.radius_px)
        inlier_mask = resid < inlier_threshold_px
        n_inliers = int(np.sum(inlier_mask))

        if n_inliers > best_inliers:
            best_inliers = n_inliers
            best = cand
            best_residual = float(np.mean(resid[inlier_mask]))

    return best, min(best_residual, 1.0)
