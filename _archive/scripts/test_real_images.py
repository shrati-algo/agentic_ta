"""Run the measurement pipeline on real trailing arm images.

Explores Hough parameter space to find the bushing hole, then runs the
full pipeline with tuned parameters.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tad.measurement.circle_detect import hough_circles, pick_innermost
from tad.measurement.models import PipelineInput
from tad.measurement.pipeline import measure_innermost_diameter
from tad.measurement.preprocessing import clahe, gaussian_blur


def explore_hough(image: np.ndarray, label: str) -> None:
    """Scan different param2 values to find the bushing hole."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    norm = clahe(gray, clip_limit=3.0, tile_grid_size=(8, 8))
    blurred = gaussian_blur(norm, kernel=5)
    h, w = image.shape[:2]

    print(f"\n  Hough scan — looking for the bushing (r >= 60 px):")
    for p2 in [60, 50, 45, 40, 35]:
        circles = hough_circles(
            blurred, dp=1.2, min_dist=80,
            param1=100, param2=p2,
            min_radius=60, max_radius=250,
        )
        if circles is None:
            print(f"    param2={p2}: no circles")
            continue
        n = len(circles[0])
        sorted_c = sorted(circles[0], key=lambda c: float(c[2]))
        print(f"    param2={p2}: {n} circles found")
        for i, c in enumerate(sorted_c[:5]):
            x, y, r = float(c[0]), float(c[1]), float(c[2])
            in_centre = abs(x - w / 2) < w * 0.4 and abs(y - h / 2) < h * 0.4
            tag = " <-- IN CENTRE" if in_centre else ""
            print(f"      #{i+1}: ({x:.0f},{y:.0f}) r={r:.1f}px d={2*r:.1f}px{tag}")


def run_pipeline(image: np.ndarray, label: str, path: Path) -> None:
    """Run the full pipeline with tuned params for real images."""
    # The bushing hole in these 3072x2048 images has radius ~80-120 px.
    # We need min_radius=60 to skip bolt holes, and param2=45 to reduce noise.
    inp = PipelineInput(
        image_bgr=image,
        calibration_mm_per_px=0.08234,
        algo_params_version="algo-1.2.0",
        clahe_clip_limit=3.0,
        clahe_tile_grid_size=(8, 8),
        blur_kernel=5,
        canny_lower_ratio=0.66,
        canny_upper_ratio=1.33,
        hough_dp=1.2,
        hough_min_dist=80,
        hough_param1=100,
        hough_param2=45,
        hough_min_radius_px=60,
        hough_max_radius_px=250,
        center_inner_fraction=0.8,
        ransac_iterations=300,
        ransac_inlier_threshold_px=1.5,
        ransac_seed=42,
        conf_pass=0.85,
        conf_review=0.60,
        tolerance_min_mm=0.0,
        tolerance_max_mm=9999.0,
    )
    output = measure_innermost_diameter(inp)

    print(f"\n  Pipeline result ({label}):")
    print(f"    Status:       {output.status}")
    if output.diameter_mm is not None:
        print(f"    Diameter:     {output.diameter_mm:.3f} mm")
    else:
        print(f"    Diameter:     N/A")
    if output.confidence is not None:
        print(f"    Confidence:   {output.confidence:.4f}")
    if output.circle:
        cx, cy, r = output.circle
        print(f"    Circle:       centre=({cx}, {cy}), radius={r:.2f} px")
        print(f"    Diameter px:  {2*r:.2f} px")
    if output.error_code:
        print(f"    Error:        {output.error_code}")

    debug_path = path.with_name(path.stem + "_debug.jpg")
    cv2.imwrite(str(debug_path), output.annotated_image)
    print(f"    Debug image:  {debug_path}")


def main() -> None:
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "images"

    for name, label in [
        ("cam18jdleofhtlhj6_L.jpg", "LEFT (Cam1)"),
        ("cam18jdleofhtlhj6_R.jpg", "RIGHT (Cam2)"),
    ]:
        path = fixtures / name
        if not path.exists():
            print(f"  File not found: {path}")
            continue

        print(f"\n{'='*70}")
        print(f"  {label}: {name}")
        print(f"{'='*70}")

        image = cv2.imread(str(path))
        h, w = image.shape[:2]
        print(f"  Resolution: {w} x {h}")

        explore_hough(image, label)
        run_pipeline(image, label, path)

    print(f"\n{'='*70}")
    print("  Done.")


if __name__ == "__main__":
    main()
