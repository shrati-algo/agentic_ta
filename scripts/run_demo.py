"""Run the backend locally with in-memory storage -- no Docker required.

Use this for UI demos and smoke-testing without provisioning Postgres or MinIO.
Sessions, measurements, chassis records, and debug JPEGs all live in RAM and
are thrown away on restart.

    python scripts/run_demo.py
    # serves on http://localhost:8000

Open http://localhost:5173/home in a second terminal with `make dev-ui`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import uvicorn

from tad.api.app import create_app
from tad.config.algo_params import load_algo_params
from tad.config.calibration import load_calibration
from tad.config.settings import Settings
from tad.persistence.blob_store import InMemoryBlobStore

# Import the fakes used by integration tests -- they double as an in-memory
# "database" for the demo.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tests.fakes import (  # noqa: E402
    InMemoryChassisRepository,
    InMemoryMeasurementRepository,
    InMemorySessionRepository,
)


def _ensure_image_dirs() -> tuple[Path, Path]:
    """Create the watched folders so the readiness probe passes."""
    left = Path.home() / ".tad" / "images" / "left"
    right = Path.home() / ".tad" / "images" / "right"
    left.mkdir(parents=True, exist_ok=True)
    right.mkdir(parents=True, exist_ok=True)
    return left, right


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    configs = repo_root / "configs"
    left_dir, right_dir = _ensure_image_dirs()

    settings = Settings(
        db_dsn="postgresql+psycopg://unused/unused",
        minio_endpoint="unused",
        minio_access_key="unused",
        minio_secret_key="unused",
        minio_bucket="tad-debug",
        images_left_dir=str(left_dir),
        images_right_dir=str(right_dir),
        algo_params_version="algo-1.3.0",
        default_calibration_left=str(configs / "calibration" / "cal-2026-03-14-L.yaml"),
        default_calibration_right=str(configs / "calibration" / "cal-2026-03-14-R.yaml"),
        log_level="INFO",
    )

    # Demo-friendly algo params.  Targeted at the yca_valid fixture set
    # (real bushings measure ~18-22 mm here) so the dashboard shows a
    # proper mix of PASS / REVIEW / FAIL instead of one flat colour.
    #
    # Per-camera classification (evaluate_status):
    #   |d - target| <= ok_band_mm        (1.0 mm)  -> PASS   (Okay)
    #   |d - target| <= somewhat_ok_band  (1.5 mm)  -> REVIEW (Somewhat Okay)
    #   outside that window                         -> FAIL   (Not Okay)
    #
    # Chassis-level combination (aggregator.combine_status):
    #   worst of (left_status, right_status) via the 4x4 matrix
    #   then downgrade PASS -> REVIEW when
    #   |d_left - d_right| > asymmetry_threshold_mm (2.5 mm).
    algo = load_algo_params(settings.algo_params_version, base_dir=configs / "algo_params")
    algo = algo.model_copy(
        update={
            "target": algo.target.model_copy(
                update={"diameter_mm": 20.0, "radius_tolerance_mm": 2.0}
            ),
            "tolerance": algo.tolerance.model_copy(
                update={
                    "min_mm": 15.0,
                    "max_mm": 25.0,
                    "ok_band_mm": 1.0,
                    "somewhat_ok_band_mm": 1.5,
                    "asymmetry_threshold_mm": 2.5,
                }
            ),
            "hough": algo.hough.model_copy(update={"param2": 15}),
        }
    )

    app = create_app(
        settings=settings,
        algo_params=algo,
        left_calibration=load_calibration(settings.default_calibration_left),
        right_calibration=load_calibration(settings.default_calibration_right),
        session_repo=InMemorySessionRepository(),
        meas_repo=InMemoryMeasurementRepository(),
        chassis_repo=InMemoryChassisRepository(),
        blob_store=InMemoryBlobStore(),
        start_watchers=True,
        run_consumer=True,
    )

    print("\n" + "=" * 70)
    print("  TAD backend (DEMO MODE -- in-memory, no Docker required)")
    print("=" * 70)
    print(f"  Image folder  (left):  {left_dir}")
    print(f"  Image folder  (right): {right_dir}")
    print(f"  Calibration   (left):  {settings.default_calibration_left}")
    print(f"  Calibration   (right): {settings.default_calibration_right}")
    print(f"  Algo params:           {settings.algo_params_version}")
    print("  API docs:              http://localhost:8000/docs")
    print("  Frontend (Vite):       http://localhost:5173/home")
    print("=" * 70 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")


if __name__ == "__main__":
    main()
