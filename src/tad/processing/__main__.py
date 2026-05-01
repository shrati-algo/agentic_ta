"""CLI entry point: ``python -m tad.processing <image> <calibration_yaml>``.

Runs the measurement pipeline on a single image and prints the result.
Useful for quick manual testing and debugging.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2

from tad.config.algo_params import load_algo_params
from tad.config.calibration import load_calibration
from tad.processing.models import PipelineInput
from tad.processing.pipeline import measure_innermost_diameter


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python -m tad.processing <image_path> <calibration_yaml>")
        print("  Optional: pass algo_params version as 3rd arg (default: algo-1.3.0)")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    cal_path = Path(sys.argv[2])
    algo_version = sys.argv[3] if len(sys.argv) > 3 else "algo-1.3.0"

    image = cv2.imread(str(image_path))
    if image is None:
        print(f"ERROR: cannot read image: {image_path}")
        sys.exit(1)

    cal = load_calibration(cal_path)
    params = load_algo_params(algo_version)

    inp = PipelineInput(
        image_bgr=image,
        calibration_mm_per_px=cal.mm_per_px,
        algo_params_version=params.version,
        blur_kernel=params.blur.kernel,
        threshold_block_size=params.threshold.block_size,
        threshold_c=params.threshold.c,
        morph_kernel_size=params.morphology.kernel_size,
        morph_iterations=params.morphology.iterations,
        contour_min_area=params.contour.min_area,
        hough_dp=params.hough.dp,
        hough_min_dist=params.hough.min_dist,
        hough_param1=params.hough.param1,
        hough_param2=params.hough.param2,
        target_diameter_mm=params.target.diameter_mm,
        radius_tolerance_mm=params.target.radius_tolerance_mm,
        ok_band_mm=params.tolerance.ok_band_mm,
        somewhat_ok_band_mm=params.tolerance.somewhat_ok_band_mm,
        tolerance_min_mm=params.tolerance.min_mm,
        tolerance_max_mm=params.tolerance.max_mm,
    )

    output = measure_innermost_diameter(inp)

    print(f"Status:      {output.status}")
    if output.diameter_mm is not None:
        print(f"Diameter:    {output.diameter_mm:.3f} mm")
    else:
        print("Diameter:    N/A")
    if output.confidence is not None:
        print(f"Confidence:  {output.confidence:.3f}")
    else:
        print("Confidence:  N/A")
    if output.circle:
        print(f"Circle:      {output.circle}")
    else:
        print("Circle:      N/A")
    if output.error_code:
        print(f"Error:       {output.error_code}")

    out_path = image_path.with_name(image_path.stem + "_debug.jpg")
    cv2.imwrite(str(out_path), output.annotated_image)
    print(f"Debug image: {out_path}")


if __name__ == "__main__":
    main()
