"""Shared fixtures for integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tad.api.app import create_app
from tad.config.algo_params import load_algo_params
from tad.config.calibration import load_calibration
from tad.config.settings import Settings
from tad.persistence.blob_store import InMemoryBlobStore
from tests.fakes import (
    InMemoryChassisRepository,
    InMemoryMeasurementRepository,
    InMemorySessionRepository,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "images"
CONFIGS = REPO_ROOT / "configs"


@pytest.fixture
def settings_for_test(tmp_path: Path) -> Settings:
    """Minimal Settings instance with empty watched folders."""
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    return Settings(
        db_dsn="postgresql+psycopg://unused/unused",
        minio_endpoint="unused",
        minio_access_key="unused",
        minio_secret_key="unused",
        minio_bucket="tad-debug",
        images_left_dir=str(left),
        images_right_dir=str(right),
        algo_params_version="algo-1.3.0",
        default_calibration_left=str(CONFIGS / "calibration" / "cal-2026-03-14-L.yaml"),
        default_calibration_right=str(CONFIGS / "calibration" / "cal-2026-03-14-R.yaml"),
        asymmetry_threshold_mm=0.15,
        queue_max_size=64,
        log_level="WARNING",
        demo_enabled=True,
    )


@pytest.fixture
def app_with_fakes(settings_for_test: Settings) -> Iterator[TestClient]:
    """FastAPI app backed entirely by in-memory repos + blob store."""
    algo_params = load_algo_params(
        settings_for_test.algo_params_version, base_dir=CONFIGS / "algo_params"
    )
    left_cal = load_calibration(settings_for_test.default_calibration_left)
    right_cal = load_calibration(settings_for_test.default_calibration_right)

    app = create_app(
        settings=settings_for_test,
        algo_params=algo_params,
        left_calibration=left_cal,
        right_calibration=right_cal,
        session_repo=InMemorySessionRepository(),
        meas_repo=InMemoryMeasurementRepository(),
        chassis_repo=InMemoryChassisRepository(),
        blob_store=InMemoryBlobStore(),
        start_watchers=False,  # tests inject items directly
        run_consumer=False,  # tests drive process_item synchronously
    )
    with TestClient(app) as client:
        client.app_state = app.state  # type: ignore[attr-defined]
        yield client
