"""Generate test fixture images for the image validator tests.

Run once: python tests/fixtures/generate_fixtures.py
"""

from pathlib import Path

import cv2
import numpy as np

OUT = Path(__file__).parent / "images"
OUT.mkdir(parents=True, exist_ok=True)


def _circle_image(w: int, h: int, *, blur: bool = False) -> np.ndarray:
    """Create a synthetic 3-channel image with a circle and some texture."""
    rng = np.random.default_rng(seed=42)
    img = rng.integers(80, 180, size=(h, w, 3), dtype=np.uint8)
    # Draw a circle in the centre
    cx, cy, r = w // 2, h // 2, min(w, h) // 6
    cv2.circle(img, (cx, cy), r, (200, 200, 200), 2)
    cv2.circle(img, (cx, cy), r // 2, (220, 220, 220), 2)
    if blur:
        img = cv2.GaussianBlur(img, (51, 51), 0)
    return img


# --- Valid pair (meeting all TRD 5.1 gates) --------------------------------
valid = _circle_image(2048, 1536)
cv2.imwrite(str(OUT / "MALBB51BLPM123456_L.jpg"), valid)
cv2.imwrite(str(OUT / "MALBB51BLPM123456_R.jpg"), valid)

# --- Blurry image (Laplacian variance < 100) --------------------------------
blurry = _circle_image(2048, 1536, blur=True)
cv2.imwrite(str(OUT / "blurry.jpg"), blurry)

# --- Too small resolution ---------------------------------------------------
small = _circle_image(640, 480)
cv2.imwrite(str(OUT / "too_small.jpg"), small)

# --- Truncated JPEG (corrupt) -----------------------------------------------
valid_bytes = (OUT / "MALBB51BLPM123456_L.jpg").read_bytes()
(OUT / "truncated.jpg").write_bytes(valid_bytes[: len(valid_bytes) // 2])

# --- Overexposed (mean > 220) — note: numpy shape is (height, width, channels) ---
bright = np.full((1536, 2048, 3), 240, dtype=np.uint8)
cv2.imwrite(str(OUT / "overexposed.jpg"), bright)

# --- Underexposed (mean < 40) -----------------------------------------------
dark = np.full((1536, 2048, 3), 20, dtype=np.uint8)
cv2.imwrite(str(OUT / "underexposed.jpg"), dark)

# --- Bad filename (not matching convention) ----------------------------------
cv2.imwrite(str(OUT / "bad_name.jpg"), valid)

print(f"Generated fixtures in {OUT}")
for p in sorted(OUT.iterdir()):
    print(f"  {p.name}  ({p.stat().st_size:,} bytes)")
