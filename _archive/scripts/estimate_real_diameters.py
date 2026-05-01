"""Estimate bushing diameter on the real trailing-arm images.

The generic "pick smallest in central region" heuristic fails here because
the cluttered plate texture produces many phantom Hough circles. For these
real images we apply a smarter selection: among the Hough candidates, pick
the circle whose **interior is darkest** (the bushing is a hole through the
plate, so its interior is much darker than the surrounding illuminated plate).

Also produces a clean annotated debug image with just the selected circle.
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


def _mean_interior_intensity(gray: np.ndarray, cx: int, cy: int, r: float) -> float:
    """Mean intensity of the disk interior (excluding the edge ring)."""
    h, w = gray.shape[:2]
    # Use 70% of the radius to avoid sampling the rim
    rr = int(r * 0.7)
    y1, y2 = max(0, cy - rr), min(h, cy + rr)
    x1, x2 = max(0, cx - rr), min(w, cx + rr)
    if y2 <= y1 or x2 <= x1:
        return 255.0
    patch = gray[y1:y2, x1:x2]

    # Circular mask within the patch
    yy, xx = np.ogrid[: patch.shape[0], : patch.shape[1]]
    mask = (yy - (cy - y1)) ** 2 + (xx - (cx - x1)) ** 2 <= rr * rr
    if not mask.any():
        return 255.0
    return float(patch[mask].mean())


def _mean_ring_intensity(gray: np.ndarray, cx: int, cy: int, r: float) -> float:
    """Mean intensity of an annulus surrounding the circle (the 'plate')."""
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


def find_bushing(
    image: np.ndarray,
    *,
    min_radius: int = 30,
    max_radius: int = 120,
    param2: int = 30,
) -> tuple[InnerCircle, float, np.ndarray] | None:
    """Detect the bushing (darkest circular hole) in the plate.

    Restricted to small-to-medium radii (30-120 px) to target the inner
    bushing hole rather than the outer rim/boss surrounding it.  Also
    requires a strong dark/bright contrast (interior must be much darker
    than the surrounding plate).
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    norm = clahe(gray, clip_limit=3.0, tile_grid_size=(8, 8))
    blurred = gaussian_blur(norm, kernel=5)

    circles = hough_circles(
        blurred,
        dp=1.2,
        min_dist=60,
        param1=100,
        param2=param2,
        min_radius=min_radius,
        max_radius=max_radius,
    )
    if circles is None:
        return None

    # Score every candidate by (surround_brightness - interior_brightness).
    # The bushing hole is dark inside a bright plate, so this contrast
    # should be strongly positive and much larger than for phantom circles
    # in the plate texture.
    h, w = image.shape[:2]
    candidates = []
    for circ in circles[0]:
        x, y, r = float(circ[0]), float(circ[1]), float(circ[2])
        # Must be within the centre 80% of the frame
        if abs(x - w / 2) > w * 0.4 or abs(y - h / 2) > h * 0.4:
            continue
        interior = _mean_interior_intensity(gray, int(x), int(y), r)
        surround = _mean_ring_intensity(gray, int(x), int(y), r)
        contrast = surround - interior
        # Require the hole to be meaningfully darker than the surround
        if contrast < 15.0:
            continue
        candidates.append((contrast, interior, x, y, r))

    if not candidates:
        return None

    # Sort descending by contrast (biggest dark-on-bright = the hole)
    candidates.sort(key=lambda c: -c[0])
    contrast, interior_intensity, x, y, r = candidates[0]

    seed = InnerCircle(cx=int(round(x)), cy=int(round(y)), radius_px=r, peak=1.0)

    # Refine with RANSAC using the Canny edge map
    edges = cv2.Canny(blurred, int(np.median(blurred) * 0.66), int(np.median(blurred) * 1.33))
    refined, residual = refine_subpixel(
        edges, seed, iterations=300, inlier_threshold_px=1.5, rng_seed=42
    )

    # Build annotated image
    annotated = image.copy()
    cv2.circle(annotated, (refined.cx, refined.cy), int(refined.radius_px), (0, 255, 0), 4)
    cv2.circle(annotated, (refined.cx, refined.cy), 5, (0, 255, 0), -1)

    return refined, residual, annotated


def main() -> None:
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "images"

    mm_per_px = 0.08234  # default calibration

    results: list[dict] = []

    for name, label in [
        ("cam18jdleofhtlhj6_L.jpg", "LEFT (Cam1)"),
        ("cam18jdleofhtlhj6_R.jpg", "RIGHT (Cam2)"),
    ]:
        path = fixtures / name
        if not path.exists():
            print(f"  File not found: {path}")
            continue

        print(f"\n{'=' * 70}")
        print(f"  {label}: {name}")
        print(f"{'=' * 70}")

        image = cv2.imread(str(path))
        h, w = image.shape[:2]
        print(f"  Resolution:       {w} x {h}")

        result = find_bushing(image)
        if result is None:
            print("  ERROR: no bushing candidate found")
            continue

        refined, residual, annotated = result
        diameter_px = 2.0 * refined.radius_px
        diameter_mm = diameter_px * mm_per_px

        print(f"  Bushing centre:   ({refined.cx}, {refined.cy}) px")
        print(f"  Radius:           {refined.radius_px:.2f} px")
        print(f"  Diameter:         {diameter_px:.2f} px")
        print(f"  Diameter (mm):    {diameter_mm:.3f} mm   [at mm_per_px={mm_per_px}]")
        print(f"  RANSAC residual:  {residual:.4f}")

        # Save clean annotation
        font = cv2.FONT_HERSHEY_SIMPLEX
        cv2.putText(
            annotated,
            f"d = {diameter_mm:.2f} mm",
            (10, 60),
            font,
            1.5,
            (0, 255, 0),
            3,
        )
        cv2.putText(
            annotated,
            f"({diameter_px:.1f} px)",
            (10, 110),
            font,
            1.0,
            (255, 255, 255),
            2,
        )

        debug_path = path.with_name(path.stem + "_measured.jpg")
        cv2.imwrite(str(debug_path), annotated)
        print(f"  Debug image:      {debug_path}")

        results.append(
            {
                "label": label,
                "diameter_px": diameter_px,
                "diameter_mm": diameter_mm,
                "radius_px": refined.radius_px,
                "centre": (refined.cx, refined.cy),
            }
        )

    # Summary
    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    for r in results:
        print(
            f"  {r['label']:15s}  d = {r['diameter_mm']:.3f} mm "
            f"({r['diameter_px']:.1f} px)  r = {r['radius_px']:.2f} px  "
            f"centre = {r['centre']}"
        )

    if len(results) == 2:
        left_mm = results[0]["diameter_mm"]
        right_mm = results[1]["diameter_mm"]
        avg = (left_mm + right_mm) / 2
        asym = abs(left_mm - right_mm)
        print()
        print(f"  Average diameter:  {avg:.3f} mm")
        print(f"  Asymmetry (|L-R|): {asym:.3f} mm")
        print()
        print(f"  Note: at mm_per_px = {mm_per_px}, the measured diameter is")
        print(f"        computed directly from the detected pixel radius.")
        print(f"        Real calibration for this specific plant fixture")
        print(f"        would need to be run to get dimensionally correct mm.")


if __name__ == "__main__":
    main()
