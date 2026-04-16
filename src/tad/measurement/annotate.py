"""Render an annotated debug image showing the measurement result.

Two circles are drawn when a measurement succeeds:
    - **Detected** circle (status colour, thick): what the pipeline measured.
    - **Target** reference circle (green, thin): ``target_diameter_mm``
      drawn around the detected centre for visual comparison.

A text panel in the top-left reports diameter, status, and confidence.
"""

from __future__ import annotations

from typing import Any, Literal

import cv2
import numpy as np

from tad.measurement.models import InnerCircle

# Colours (BGR)
_GREEN = (0, 200, 0)
_RED = (0, 0, 220)
_AMBER = (0, 180, 255)
_GREY = (160, 160, 160)
_WHITE = (255, 255, 255)
_REFERENCE = (0, 255, 0)  # bright green for the target reference circle

_STATUS_COLOUR: dict[str, tuple[int, int, int]] = {
    "PASS": _GREEN,
    "FAIL": _RED,
    "REVIEW": _AMBER,
    "ERROR": _GREY,
}


def render_debug_image(
    image_bgr: np.ndarray[Any, Any],
    circle: InnerCircle | None,
    diameter_mm: float | None,
    status: Literal["PASS", "FAIL", "REVIEW", "ERROR"],
    confidence: float | None,
    *,
    target_diameter_mm: float | None = None,
    mm_per_px: float | None = None,
) -> np.ndarray[Any, Any]:
    """Draw measurement annotations on a copy of the source image."""
    canvas = image_bgr.copy()
    colour = _STATUS_COLOUR.get(status, _GREY)

    # Target reference circle (if calibration and target are supplied)
    if (
        circle is not None
        and target_diameter_mm is not None
        and mm_per_px is not None
        and mm_per_px > 0
    ):
        target_r = int(round((target_diameter_mm / 2.0) / mm_per_px))
        cv2.circle(canvas, (circle.cx, circle.cy), target_r, _REFERENCE, 2)

    # Detected circle (highlighted)
    if circle is not None:
        cv2.circle(canvas, (circle.cx, circle.cy), int(circle.radius_px), colour, 3)
        cv2.circle(canvas, (circle.cx, circle.cy), 4, colour, -1)

    # Text overlay
    h = canvas.shape[0]
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = max(0.6, h / 2000.0)
    thickness = max(1, int(h / 800))
    y_pos = int(40 * font_scale)
    line_h = int(50 * font_scale)

    if diameter_mm is not None:
        text = f"Diameter: {diameter_mm:.3f} mm"
        cv2.putText(canvas, text, (10, y_pos), font, font_scale, colour, thickness)
        y_pos += line_h

    cv2.putText(canvas, f"Status: {status}", (10, y_pos), font, font_scale, colour, thickness)
    y_pos += line_h

    if confidence is not None:
        cv2.putText(
            canvas,
            f"Confidence: {confidence:.3f}",
            (10, y_pos),
            font,
            font_scale,
            _WHITE,
            thickness,
        )
        y_pos += line_h

    if target_diameter_mm is not None:
        cv2.putText(
            canvas,
            f"Target: {target_diameter_mm:.2f} mm",
            (10, y_pos),
            font,
            font_scale * 0.8,
            _REFERENCE,
            thickness,
        )

    return canvas
