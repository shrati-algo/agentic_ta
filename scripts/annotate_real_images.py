"""Create fully-annotated debug images showing the bushing measurement.

Draws: detected circle, centre crosshair, diameter line with end caps,
and a labelled info panel with all the key numbers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tad.measurement.circle_detect import hough_circles
from tad.measurement.models import InnerCircle
from tad.measurement.preprocessing import clahe, gaussian_blur
from tad.measurement.ransac_refine import refine_subpixel


# --- reused helpers (from estimate_real_diameters.py) ----------------------
def _mean_interior_intensity(gray: np.ndarray, cx: int, cy: int, r: float) -> float:
    h, w = gray.shape[:2]
    rr = int(r * 0.7)
    y1, y2 = max(0, cy - rr), min(h, cy + rr)
    x1, x2 = max(0, cx - rr), min(w, cx + rr)
    if y2 <= y1 or x2 <= x1:
        return 255.0
    patch = gray[y1:y2, x1:x2]
    yy, xx = np.ogrid[: patch.shape[0], : patch.shape[1]]
    mask = (yy - (cy - y1)) ** 2 + (xx - (cx - x1)) ** 2 <= rr * rr
    if not mask.any():
        return 255.0
    return float(patch[mask].mean())


def _mean_ring_intensity(gray: np.ndarray, cx: int, cy: int, r: float) -> float:
    h, w = gray.shape[:2]
    r_in = int(r * 1.3)
    r_out = int(r * 2.0)
    y1, y2 = max(0, cy - r_out), min(h, cy + r_out)
    x1, x2 = max(0, cx - r_out), min(w, cx + r_out)
    if y2 <= y1 or x2 <= x1:
        return 0.0
    patch = gray[y1:y2, x1:x2]
    yy, xx = np.ogrid[: patch.shape[0], : patch.shape[1]]
    d2 = (yy - (cy - y1)) ** 2 + (xx - (cx - x1)) ** 2
    mask = (d2 >= r_in * r_in) & (d2 <= r_out * r_out)
    if not mask.any():
        return 0.0
    return float(patch[mask].mean())


def find_bushing(image: np.ndarray) -> tuple[InnerCircle, float] | None:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    norm = clahe(gray, clip_limit=3.0, tile_grid_size=(8, 8))
    blurred = gaussian_blur(norm, kernel=5)

    circles = hough_circles(
        blurred, dp=1.2, min_dist=60,
        param1=100, param2=30,
        min_radius=30, max_radius=120,
    )
    if circles is None:
        return None

    h, w = image.shape[:2]
    candidates = []
    for circ in circles[0]:
        x, y, r = float(circ[0]), float(circ[1]), float(circ[2])
        if abs(x - w / 2) > w * 0.4 or abs(y - h / 2) > h * 0.4:
            continue
        interior = _mean_interior_intensity(gray, int(x), int(y), r)
        surround = _mean_ring_intensity(gray, int(x), int(y), r)
        contrast = surround - interior
        if contrast < 15.0:
            continue
        candidates.append((contrast, x, y, r))

    if not candidates:
        return None

    candidates.sort(key=lambda c: -c[0])
    _, x, y, r = candidates[0]
    seed = InnerCircle(cx=int(round(x)), cy=int(round(y)), radius_px=r, peak=1.0)

    edges = cv2.Canny(blurred, int(np.median(blurred) * 0.66), int(np.median(blurred) * 1.33))
    refined, residual = refine_subpixel(
        edges, seed, iterations=300, inlier_threshold_px=1.5, rng_seed=42
    )
    return refined, residual


# --- annotation -------------------------------------------------------------
GREEN = (0, 255, 0)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (0, 255, 255)
RED = (0, 0, 255)


def draw_panel(
    canvas: np.ndarray,
    lines: list[tuple[str, tuple[int, int, int]]],
    anchor: tuple[int, int] = (20, 20),
) -> None:
    """Draw a semi-transparent info panel with labelled lines."""
    x0, y0 = anchor
    font = cv2.FONT_HERSHEY_SIMPLEX
    line_h = 48
    pad = 20

    # Measure text width
    max_w = 0
    for text, _ in lines:
        (tw, _th), _ = cv2.getTextSize(text, font, 1.0, 2)
        max_w = max(max_w, tw)

    panel_w = max_w + 2 * pad
    panel_h = line_h * len(lines) + 2 * pad

    # Semi-transparent background
    overlay = canvas.copy()
    cv2.rectangle(overlay, (x0, y0), (x0 + panel_w, y0 + panel_h), BLACK, -1)
    cv2.addWeighted(overlay, 0.7, canvas, 0.3, 0, canvas)

    # Border
    cv2.rectangle(canvas, (x0, y0), (x0 + panel_w, y0 + panel_h), GREEN, 2)

    # Text lines
    for i, (text, color) in enumerate(lines):
        y = y0 + pad + (i + 1) * line_h - 12
        cv2.putText(canvas, text, (x0 + pad, y), font, 1.0, color, 2, cv2.LINE_AA)


def annotate(
    image: np.ndarray,
    circle: InnerCircle,
    residual: float,
    mm_per_px: float,
    camera_label: str,
) -> np.ndarray:
    canvas = image.copy()
    cx, cy, r = circle.cx, circle.cy, circle.radius_px
    diameter_px = 2.0 * r
    diameter_mm = diameter_px * mm_per_px

    # Main detected circle (bright green, thick)
    cv2.circle(canvas, (cx, cy), int(r), GREEN, 4, cv2.LINE_AA)

    # Centre crosshair
    crosshair = 30
    cv2.line(canvas, (cx - crosshair, cy), (cx + crosshair, cy), GREEN, 3)
    cv2.line(canvas, (cx, cy - crosshair), (cx, cy + crosshair), GREEN, 3)
    cv2.circle(canvas, (cx, cy), 5, GREEN, -1)

    # Diameter line with end caps (yellow, offset slightly)
    y_offset = int(r) + 40
    x1 = cx - int(r)
    x2 = cx + int(r)
    yd = cy - y_offset
    cv2.line(canvas, (x1, yd), (x2, yd), YELLOW, 3)
    # End caps (short vertical ticks)
    tick = 20
    cv2.line(canvas, (x1, yd - tick), (x1, yd + tick), YELLOW, 3)
    cv2.line(canvas, (x2, yd - tick), (x2, yd + tick), YELLOW, 3)
    # Label on the diameter line
    label = f"{diameter_px:.1f} px"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
    tx = cx - tw // 2
    ty = yd - 15
    cv2.rectangle(canvas, (tx - 5, ty - th - 5), (tx + tw + 5, ty + 5), BLACK, -1)
    cv2.putText(canvas, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 1.0, YELLOW, 2, cv2.LINE_AA)

    # Info panel in the top-left
    panel_lines = [
        (f"{camera_label}", GREEN),
        (f"Diameter: {diameter_mm:.3f} mm", WHITE),
        (f"Diameter: {diameter_px:.2f} px", CYAN),
        (f"Radius:   {r:.2f} px", WHITE),
        (f"Centre:   ({cx}, {cy})", WHITE),
        (f"mm/px:    {mm_per_px}", WHITE),
        (f"RANSAC residual: {residual:.3f}", WHITE),
    ]
    draw_panel(canvas, panel_lines, anchor=(30, 30))

    return canvas


def main() -> None:
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "images"
    mm_per_px = 0.08234

    results = []
    for name, label in [
        ("cam18jdleofhtlhj6_L.jpg", "LEFT (Cam1)"),
        ("cam18jdleofhtlhj6_R.jpg", "RIGHT (Cam2)"),
    ]:
        path = fixtures / name
        if not path.exists():
            print(f"  File not found: {path}")
            continue

        image = cv2.imread(str(path))
        result = find_bushing(image)
        if result is None:
            print(f"  {label}: no bushing detected")
            continue

        refined, residual = result
        annotated = annotate(image, refined, residual, mm_per_px, label)

        out_path = path.with_name(path.stem + "_annotated.jpg")
        cv2.imwrite(str(out_path), annotated)
        print(
            f"  {label}: d = {2 * refined.radius_px * mm_per_px:.3f} mm  "
            f"({2 * refined.radius_px:.2f} px)  -> {out_path.name}"
        )
        results.append((label, refined, residual))

    # Combined side-by-side comparison image
    if len(results) == 2:
        left_path = fixtures / "cam18jdleofhtlhj6_L.jpg"
        right_path = fixtures / "cam18jdleofhtlhj6_R.jpg"
        left = annotate(cv2.imread(str(left_path)), results[0][1], results[0][2], mm_per_px, "LEFT (Cam1)")
        right = annotate(cv2.imread(str(right_path)), results[1][1], results[1][2], mm_per_px, "RIGHT (Cam2)")

        # Resize to common width for side-by-side
        target_w = 1500
        scale_l = target_w / left.shape[1]
        scale_r = target_w / right.shape[1]
        left_r = cv2.resize(left, (target_w, int(left.shape[0] * scale_l)))
        right_r = cv2.resize(right, (target_w, int(right.shape[0] * scale_r)))

        # Stack vertically with a separator
        sep = np.zeros((20, target_w, 3), dtype=np.uint8)
        combined = np.vstack([left_r, sep, right_r])

        # Title bar at the top of combined image
        title_h = 120
        title_bar = np.zeros((title_h, target_w, 3), dtype=np.uint8)
        d_l = 2 * results[0][1].radius_px * mm_per_px
        d_r = 2 * results[1][1].radius_px * mm_per_px
        avg = (d_l + d_r) / 2
        asym = abs(d_l - d_r)
        cv2.putText(
            title_bar,
            f"Bushing measurement  |  avg = {avg:.3f} mm  |  asymmetry = {asym:.3f} mm",
            (30, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.2, WHITE, 2, cv2.LINE_AA,
        )
        cv2.putText(
            title_bar,
            f"Phase 3 measurement pipeline -- classical CV, no ML",
            (30, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.9, CYAN, 2, cv2.LINE_AA,
        )
        combined = np.vstack([title_bar, combined])

        combined_path = fixtures / "cam18jdleofhtlhj6_comparison.jpg"
        cv2.imwrite(str(combined_path), combined)
        print(f"\n  Side-by-side comparison: {combined_path}")


if __name__ == "__main__":
    main()
