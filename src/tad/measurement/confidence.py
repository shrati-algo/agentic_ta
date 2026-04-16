"""Confidence scoring and status evaluation."""

from __future__ import annotations

from typing import Literal


def score(
    *,
    hough_peak: float,
    ransac_residual: float,
) -> float:
    """Compute a confidence score in [0, 1].

    Parameters
    ----------
    hough_peak:
        Hough accumulator strength (normalised, 0-1).
    ransac_residual:
        Mean RANSAC inlier residual (lower is better, capped at 1.0).

    Returns
    -------
    float
        Confidence in ``[0, 1]``.
    """
    raw = hough_peak * (1.0 - ransac_residual)
    return max(0.0, min(1.0, raw))


def evaluate_status(
    diameter_mm: float,
    confidence: float,
    *,
    conf_pass: float = 0.85,
    conf_review: float = 0.60,
    tolerance_min_mm: float = 47.0,
    tolerance_max_mm: float = 47.5,
) -> Literal["PASS", "FAIL", "REVIEW", "ERROR"]:
    """Determine measurement status from diameter and confidence.

    Decision logic (TRD Section 6, step 13):
        - PASS  : confidence >= conf_pass AND diameter in tolerance
        - REVIEW: confidence in [conf_review, conf_pass) regardless of diameter,
                  OR confidence >= conf_pass but diameter outside tolerance
                  -> actually FAIL if diameter is outside tolerance with high confidence
        - FAIL  : diameter outside tolerance
        - ERROR : confidence < conf_review

    Simplified:
        1. If confidence < conf_review -> ERROR
        2. If diameter outside tolerance -> FAIL
        3. If confidence < conf_pass -> REVIEW
        4. Otherwise -> PASS
    """
    if confidence < conf_review:
        return "ERROR"
    if diameter_mm < tolerance_min_mm or diameter_mm > tolerance_max_mm:
        return "FAIL"
    if confidence < conf_pass:
        return "REVIEW"
    return "PASS"
