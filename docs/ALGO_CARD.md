# Algorithm Card — Trailing-Arm Detection

**Algorithm version:** algo-1.3.0
**Type:** Classical CV (Gaussian blur → adaptive threshold → contours →
masked HoughCircles)
**Last updated:** 2026-05-01
**Model:** N/A — classical CV (Hough + contour)

## 1. Pipeline
1. Read JPEG (size-stable; safe_read).
2. Validate dimensions / format / not-truncated.
3. Gaussian blur → adaptive Gaussian threshold (inverted) → morphological close.
4. Extract external contours, walk largest-first.
5. For each contour, run masked `cv2.HoughCircles` constrained to
   `target_diameter_mm ± radius_tolerance_mm`.
6. First matching circle wins. mm conversion via calibration `mm_per_px`.
7. Per-camera result → Aggregator → chassis-level PASS/REVIEW/FAIL.

## 2. Parameters (current config: algo-1.3.0)
Source: `configs/algo_params/algo-1.3.0.yaml`.

| Parameter | Value | Notes |
| --------- | ----- | ----- |
| target_diameter_mm | 47.25 | from yaml |
| radius_tolerance_mm | 0.30 | from yaml |
| asymmetry_threshold_mm | 0.15 | aggregator |
| ok_band_mm | 0.20 | tolerance |
| somewhat_ok_band_mm | 0.50 | tolerance |
| tolerance.min_mm / max_mm | 47.000 / 47.500 | absolute bounds |
| blur_kernel | 5 | preprocessing |
| adaptive_block_size | 51 | threshold |
| adaptive_c | 10 | threshold |
| morph_close_kernel | 3 (1 iteration) | threshold |
| hough.dp / min_dist | 1.2 / 10 | hough |
| hough.param1 / param2 | 50 / 20 | hough |
| contour.min_area | 50.0 | contour filter |

## 3. Inputs / outputs
- Input: dual JPEGs (`<CHASSIS>_L.jpg`, `<CHASSIS>_R.jpg`) + calibration
  YAMLs.
- Output: per-camera circle (cx, cy, r_px, r_mm, confidence) + chassis-
  level status (PASS/REVIEW/FAIL).

## 4. Limits & assumptions
- Image dims roughly 500×500 px (varies with calibration).
- Single innermost circle per arm.
- Calibration is locked at session start.
- No ML — purely deterministic per (image, algo_version, calibration).

## 5. Versioning policy
- Param changes require an ADR.
- Each measurement pins `algo_version` + `calibration_version` in DB.
- Locked eval (`make eval`) MUST pass before any param bump.

## 6. Why no ML?
See `docs/decisions/ADR-001.md`.

## 7. Why Hough + contour, not Canny + RANSAC?
See `docs/decisions/ADR-008.md`.
