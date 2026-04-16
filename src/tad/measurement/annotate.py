"""Render an annotated debug image showing the measurement result.

The debug image is stored alongside every measurement record so that
operators and QA can visually verify what the system measured.
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
    all_circles: np.ndarray[Any, Any] | None = None,
) -> np.ndarray[Any, Any]:
    """Draw measurement annotations on a copy of the source image.

    Parameters
    ----------
    image_bgr:
        The original BGR image.
    circle:
        The selected innermost circle (may be ``None`` on error).
    diameter_mm:
        The measured diameter (may be ``None`` on error).
    status:
        The measurement status.
    confidence:
        The confidence score (may be ``None``).
    all_circles:
        Optional array of all detected circles to render dimmed.

    Returns
    -------
    np.ndarray
        Annotated copy of the image.
    """
    canvas = image_bgr.copy()
    colour = _STATUS_COLOUR.get(status, _GREY)

    # Draw all candidate circles dimmed
    if all_circles is not None and len(all_circles.shape) >= 2:
        for circ in all_circles[0]:
            x, y, r = int(circ[0]), int(circ[1]), int(circ[2])
            cv2.circle(canvas, (x, y), r, _GREY, 1)

    # Draw the selected circle highlighted
    if circle is not None:
        cv2.circle(canvas, (circle.cx, circle.cy), int(circle.radius_px), colour, 2)
        cv2.circle(canvas, (circle.cx, circle.cy), 3, colour, -1)

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
        text = f"Confidence: {confidence:.3f}"
        cv2.putText(canvas, text, (10, y_pos), font, font_scale, _WHITE, thickness)

    return canvas
