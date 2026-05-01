"""Diameter-band classification and confidence score.

The contour-based detector returns a circle whose radius has already
been constrained to be near the target.  Status is therefore derived
deterministically from how close the measured diameter is to the
target, using three bands:

- ``|delta| <= ok_band_mm``             -> PASS   (UI: "Okay")
- ``|delta| <= somewhat_ok_band_mm``    -> REVIEW (UI: "Somewhat Okay")
- otherwise but in [tolerance_min, max] -> FAIL   (UI: "Not Okay")
- outside absolute tolerance            -> FAIL
- no circle detected                    -> ERROR  (UI: "Error")

A confidence score in [0, 1] is reported for information: 1.0 at exact
match, decaying linearly to 0.0 at the REVIEW boundary.
"""

from __future__ import annotations

from typing import Literal

Status = Literal["PASS", "FAIL", "REVIEW", "ERROR"]


def compute_confidence(
    diameter_mm: float,
    target_mm: float,
    *,
    somewhat_ok_band_mm: float = 0.5,
) -> float:
    """Linear confidence: 1.0 at target, 0.0 at the REVIEW boundary."""
    if somewhat_ok_band_mm <= 0:
        return 1.0 if abs(diameter_mm - target_mm) < 1e-9 else 0.0
    delta = abs(diameter_mm - target_mm)
    raw = 1.0 - (delta / somewhat_ok_band_mm)
    return max(0.0, min(1.0, raw))


def evaluate_status(
    diameter_mm: float,
    target_mm: float,
    *,
    ok_band_mm: float = 0.2,
    somewhat_ok_band_mm: float = 0.5,
    tolerance_min_mm: float = 47.0,
    tolerance_max_mm: float = 47.5,
) -> Status:
    """Classify a measured diameter into PASS / REVIEW / FAIL.

    Band precedence (TRD Section 6):
        1. ``|detected - target| <= ok_band_mm``             -> PASS
        2. ``|detected - target| <= somewhat_ok_band_mm``    -> REVIEW
        3. otherwise                                         -> FAIL

    A FAIL is also returned when the diameter falls outside the
    absolute tolerance window [``tolerance_min_mm``, ``tolerance_max_mm``].
    """
    if diameter_mm < tolerance_min_mm or diameter_mm > tolerance_max_mm:
        return "FAIL"

    delta = abs(diameter_mm - target_mm)
    if delta <= ok_band_mm:
        return "PASS"
    if delta <= somewhat_ok_band_mm:
        return "REVIEW"
    return "FAIL"
