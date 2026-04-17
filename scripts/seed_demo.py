"""Seed the running demo backend with a handful of chassis measurements.

Run this while `make demo` is serving on :8000.  It starts a session,
writes matched L/R image pairs into the watched folders, and waits a
few seconds for the pipeline to process them so the dashboard fills up
live as you watch it.

    python scripts/seed_demo.py
    # or:
    make demo-seed
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import cv2
import httpx
import numpy as np


API_BASE = "http://localhost:8000"
LEFT_DIR = Path.home() / ".tad" / "images" / "left"
RIGHT_DIR = Path.home() / ".tad" / "images" / "right"


def _random_chassis_no(rng: random.Random) -> str:
    alphabet = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"  # no I, O, Q
    return "".join(rng.choice(alphabet) for _ in range(17))


def _make_image(radius_px: int, seed: int) -> bytes:
    """Synthesise a 2200x1600 bright-plate image with a dark circle.

    Matches the image-validator gates (resolution >= 2048x1536, blur
    variance >= 100, exposure in [40, 220]) and the demo algo_params
    target of 20 mm (radius ~121 px at mm_per_px=0.08234).
    """
    img = np.full((1600, 2200, 3), 215, dtype=np.uint8)
    cv2.circle(img, (1100, 800), radius_px, (30, 30, 30), -1)
    rng = np.random.default_rng(seed=seed)
    noise = rng.integers(-15, 15, size=img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    if not ok:
        msg = "cv2.imencode failed"
        raise RuntimeError(msg)
    return buf.tobytes()


def _ensure_session() -> str:
    """Return the active session id, starting one if necessary."""
    with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
        r = client.get("/v1/sessions", params={"status": "ACTIVE"})
        r.raise_for_status()
        active = r.json()
        if active:
            return str(active[0]["session_id"])

        r = client.post(
            "/v1/sessions/start",
            json={"started_by": "demo-seed", "shift": "A", "area": "Welding"},
        )
        r.raise_for_status()
        return str(r.json()["session_id"])


def _drop_pairs(count: int) -> list[str]:
    """Write ``count`` matched L/R image pairs into the watched folders.

    Mix of diameters so the dashboard shows PASS / REVIEW / FAIL rows.
    Returns the list of chassis numbers written.
    """
    LEFT_DIR.mkdir(parents=True, exist_ok=True)
    RIGHT_DIR.mkdir(parents=True, exist_ok=True)

    rng = random.Random(42)
    # Target ~20 mm  ->  radius 121 px at mm_per_px = 0.08234.
    # Mix radii so we see all the status bands populate.
    #   r=121 -> 19.93 mm  (PASS)
    #   r=127 -> 20.91 mm  (REVIEW)
    #   r=100 -> 16.47 mm  (FAIL when tolerance_min = 15.0? no -- still OK)
    # Demo algo_params tolerance is 15..25, so use r=140 for FAIL
    profiles = [121, 121, 127, 127, 140]
    chassis_nos: list[str] = []

    for i in range(count):
        chassis = _random_chassis_no(rng)
        radius = profiles[i % len(profiles)]
        jpg = _make_image(radius, seed=i)
        left_path = LEFT_DIR / f"{chassis}_L.jpg"
        right_path = RIGHT_DIR / f"{chassis}_R.jpg"
        left_path.write_bytes(jpg)
        right_path.write_bytes(jpg)
        chassis_nos.append(chassis)
        # Small pause so the dashboard animates as rows land
        time.sleep(0.3)

    return chassis_nos


def _wait_for_processing(chassis_count: int, timeout_s: float = 30.0) -> int:
    """Poll /v1/chassis until processing catches up (or we time out)."""
    deadline = time.monotonic() + timeout_s
    with httpx.Client(base_url=API_BASE, timeout=10.0) as client:
        while time.monotonic() < deadline:
            r = client.get("/v1/chassis", params={"page": 1, "page_size": 50})
            r.raise_for_status()
            total = r.json()["total"]
            if total >= chassis_count:
                return int(total)
            time.sleep(0.5)
    return int(client.get("/v1/chassis").json()["total"])


def main() -> None:
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 5

    print(f"\n[seed] posting to {API_BASE}")
    try:
        session_id = _ensure_session()
    except Exception as exc:  # noqa: BLE001
        print(f"[seed] ERROR: couldn't reach the backend at {API_BASE}.")
        print(f"       Is `make demo` running in another terminal?  ({exc})")
        sys.exit(1)

    print(f"[seed] active session: {session_id}")
    print(f"[seed] left folder:    {LEFT_DIR}")
    print(f"[seed] right folder:   {RIGHT_DIR}")
    print(f"[seed] dropping {count} matched L/R pairs...\n")

    chassis_nos = _drop_pairs(count)
    for c in chassis_nos:
        print(f"       + {c}_L.jpg  +  {c}_R.jpg")

    print(f"\n[seed] waiting for the backend to process {count} chassis...")
    total = _wait_for_processing(count)
    print(f"[seed] /v1/chassis total = {total}")
    print("[seed] open http://localhost:5173/home and watch the rows appear.")
    print("       (if the dashboard isn't running, `make dev-ui` in another terminal)\n")


if __name__ == "__main__":
    main()
