"""Annotate real trailing arm images with the algo-1.3.0 pipeline.

Uses the new contour + masked Hough detector from
``tad.measurement.pipeline``.  The ``render_debug_image`` call inside
the pipeline already draws the detected circle, a target reference
circle, and text overlays.  This script additionally composes a
side-by-side comparison image and a richer labelled panel on top of
the pipeline output.
"""

from __future__ import annotations

import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tad.config.algo_params import load_algo_params
from tad.measurement.models import PipelineInput
from tad.measurement.pipeline import measure_innermost_diameter

# Target for the cam18 bushing, observed diameter ~19.5-20.4 mm in the
# earlier exploration.  mm_per_px is the committed calibration.
TARGET_DIAMETER_MM = 20.0
MM_PER_PX = 0.08234

GREEN = (0, 255, 0)
CYAN = (255, 255, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
YELLOW = (0, 255, 255)


def build_input(image: np.ndarray) -> PipelineInput:
    params = load_algo_params("algo-1.3.0")
    return PipelineInput(
        image_bgr=image,
        calibration_mm_per_px=MM_PER_PX,
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
        hough_param2=15,  # softened for high-res real images
        target_diameter_mm=TARGET_DIAMETER_MM,
        radius_tolerance_mm=1.5,  # widen for realistic part variation
        ok_band_mm=0.4,
        somewhat_ok_band_mm=1.5,
        tolerance_min_mm=15.0,
        tolerance_max_mm=25.0,
    )


def draw_panel(canvas: np.ndarray, lines: list[tuple[str, tuple[int, int, int]]]) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    pad = 20
    line_h = 48
    max_w = 0
    for text, _ in lines:
        (tw, _th), _ = cv2.getTextSize(text, font, 1.0, 2)
        max_w = max(max_w, tw)
    panel_w = max_w + 2 * pad
    panel_h = line_h * len(lines) + 2 * pad

    overlay = canvas.copy()
    cv2.rectangle(overlay, (20, 20), (20 + panel_w, 20 + panel_h), BLACK, -1)
    cv2.addWeighted(overlay, 0.7, canvas, 0.3, 0, canvas)
    cv2.rectangle(canvas, (20, 20), (20 + panel_w, 20 + panel_h), GREEN, 2)

    for i, (text, color) in enumerate(lines):
        y = 20 + pad + (i + 1) * line_h - 12
        cv2.putText(canvas, text, (20 + pad, y), font, 1.0, color, 2, cv2.LINE_AA)


def annotate_one(image: np.ndarray, camera_label: str) -> tuple[np.ndarray, dict]:
    inp = build_input(image)
    out = measure_innermost_diameter(inp)

    # Start from the pipeline's debug image (already has detected circle +
    # target reference circle).  Replace the pipeline's top-left text block
    # with a nicer semi-transparent panel.
    canvas = out.annotated_image.copy()

    # Wipe the pipeline's text that sits in the top-left (rows 0..360 px)
    h, w = canvas.shape[:2]
    overlay = canvas.copy()
    cv2.rectangle(overlay, (0, 0), (min(700, w), 300), BLACK, -1)
    cv2.addWeighted(overlay, 0.5, canvas, 0.5, 0, canvas)

    # Diameter line with end-caps under the detected circle
    if out.circle is not None:
        cx, cy, r = out.circle
        y_off = int(r) + 50
        xa, xb = cx - int(r), cx + int(r)
        yd = cy - y_off
        cv2.line(canvas, (xa, yd), (xb, yd), YELLOW, 3)
        cv2.line(canvas, (xa, yd - 20), (xa, yd + 20), YELLOW, 3)
        cv2.line(canvas, (xb, yd - 20), (xb, yd + 20), YELLOW, 3)
        label = f"{2 * r:.1f} px"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        tx = cx - tw // 2
        ty = yd - 15
        cv2.rectangle(canvas, (tx - 6, ty - th - 6), (tx + tw + 6, ty + 6), BLACK, -1)
        cv2.putText(canvas, label, (tx, ty), cv2.FONT_HERSHEY_SIMPLEX, 1.0, YELLOW, 2, cv2.LINE_AA)

    lines: list[tuple[str, tuple[int, int, int]]] = [
        (f"{camera_label}  (algo-1.3.0)", GREEN),
    ]
    if out.diameter_mm is not None:
        lines.append((f"Diameter: {out.diameter_mm:.3f} mm", WHITE))
        lines.append((f"Diameter: {2 * out.circle[2]:.2f} px", CYAN))
        lines.append((f"Radius:   {out.circle[2]:.2f} px", WHITE))
        lines.append((f"Centre:   ({out.circle[0]}, {out.circle[1]})", WHITE))
    lines.append((f"Target:   {TARGET_DIAMETER_MM:.2f} mm", GREEN))
    lines.append((f"Status:   {out.status}", GREEN if out.status == "PASS" else CYAN))
    if out.confidence is not None:
        lines.append((f"Conf:     {out.confidence:.3f}", WHITE))
    lines.append((f"mm/px:    {MM_PER_PX}", WHITE))

    draw_panel(canvas, lines)

    return canvas, {
        "label": camera_label,
        "diameter_mm": out.diameter_mm,
        "radius_px": out.circle[2] if out.circle else None,
        "status": out.status,
        "confidence": out.confidence,
        "circle": out.circle,
    }


def main() -> None:
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "images"

    results = []
    for name, label in [
        ("cam18jdleofhtlhj6_L.jpg", "LEFT (Cam1)"),
        ("cam18jdleofhtlhj6_R.jpg", "RIGHT (Cam2)"),
    ]:
        p = fixtures / name
        if not p.exists():
            print(f"  File not found: {p}")
            continue
        image = cv2.imread(str(p))
        annotated, info = annotate_one(image, label)
        out_path = p.with_name(p.stem + "_annotated_v2.jpg")
        cv2.imwrite(str(out_path), annotated)
        print(
            f"  {label}: d = {info['diameter_mm']:.3f} mm  "
            f"status = {info['status']}  -> {out_path.name}"
        )
        results.append((annotated, info))

    # Side-by-side comparison
    if len(results) == 2:
        target_w = 1500
        imgs = []
        for img, _ in results:
            scale = target_w / img.shape[1]
            imgs.append(cv2.resize(img, (target_w, int(img.shape[0] * scale))))

        sep = np.zeros((20, target_w, 3), dtype=np.uint8)

        # Title bar
        title_h = 130
        title = np.zeros((title_h, target_w, 3), dtype=np.uint8)
        d_l = results[0][1]["diameter_mm"]
        d_r = results[1][1]["diameter_mm"]
        avg = (d_l + d_r) / 2 if d_l and d_r else None
        asym = abs(d_l - d_r) if d_l and d_r else None

        cv2.putText(
            title,
            f"algo-1.3.0  |  target = {TARGET_DIAMETER_MM:.2f} mm"
            + (f"  |  avg = {avg:.3f} mm" if avg else "")
            + (f"  |  asymmetry = {asym:.3f} mm" if asym else ""),
            (30, 55),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.1,
            WHITE,
            2,
            cv2.LINE_AA,
        )
        cv2.putText(
            title,
            "Contour + masked Hough detection (ADR-008)",
            (30, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.9,
            CYAN,
            2,
            cv2.LINE_AA,
        )

        combined = np.vstack([title, imgs[0], sep, imgs[1]])
        out_path = fixtures / "cam18jdleofhtlhj6_comparison_v2.jpg"
        cv2.imwrite(str(out_path), combined)
        print(f"\n  Side-by-side comparison: {out_path}")


if __name__ == "__main__":
    main()
