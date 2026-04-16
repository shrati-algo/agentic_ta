"""CLI entry point: ``python -m tad.measurement <image> <calibration_yaml>``.

Runs the measurement pipeline on a single image and prints the result.
Useful for quick manual testing and debugging.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

from tad.config.algo_params import load_algo_params
from tad.config.calibration import load_calibration
from tad.measurement.models import PipelineInput
from tad.measurement.pipeline import measure_innermost_diameter


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m tad.measurement <image_path> <calibration_yaml>")
        print("  Optional: pass algo_params version as 3rd arg (default: algo-1.2.0)")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    cal_path = Path(sys.argv[2])
    algo_version = sys.argv[3] if len(sys.argv) > 3 else "algo-1.2.0"

    # Load image
    image = cv2.imread(str(image_path))
    if image is None:
        print(f"ERROR: cannot read image: {image_path}")
        sys.exit(1)

    # Load calibration and algo_params
    cal = load_calibration(cal_path)
    params = load_algo_params(algo_version)

    # Build pipeline input
    inp = PipelineInput(
        image_bgr=image,
        calibration_mm_per_px=cal.mm_per_px,
        algo_params_version=params.version,
        clahe_clip_limit=params.clahe.clip_limit,
        clahe_tile_grid_size=params.clahe.tile_grid_size,
        blur_kernel=params.blur.kernel,
        canny_lower_ratio=params.canny.lower_ratio,
        canny_upper_ratio=params.canny.upper_ratio,
        hough_dp=params.hough.dp,
        hough_min_dist=params.hough.min_dist,
        hough_param1=params.hough.param1,
        hough_param2=params.hough.param2,
        hough_min_radius_px=params.hough.min_radius_px,
        hough_max_radius_px=params.hough.max_radius_px,
        center_inner_fraction=params.center_region.inner_fraction,
        ransac_iterations=params.ransac.iterations,
        ransac_inlier_threshold_px=params.ransac.inlier_threshold_px,
        ransac_seed=params.ransac.seed,
        conf_pass=params.confidence.conf_pass,
        conf_review=params.confidence.conf_review,
        tolerance_min_mm=params.tolerance.min_mm,
        tolerance_max_mm=params.tolerance.max_mm,
    )

    # Run
    output = measure_innermost_diameter(inp)

    # Print results
    print(f"Status:      {output.status}")
    print(f"Diameter:    {output.diameter_mm:.3f} mm" if output.diameter_mm else "Diameter:    N/A")
    print(f"Confidence:  {output.confidence:.3f}" if output.confidence else "Confidence:  N/A")
    print(f"Circle:      {output.circle}" if output.circle else "Circle:      N/A")
    print(f"Error:       {output.error_code}" if output.error_code else "Error:       None")

    # Save debug image
    out_path = image_path.with_name(image_path.stem + "_debug.jpg")
    cv2.imwrite(str(out_path), output.annotated_image)
    print(f"Debug image: {out_path}")


if __name__ == "__main__":
    main()
