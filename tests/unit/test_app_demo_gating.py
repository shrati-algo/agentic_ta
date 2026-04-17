"""STORY-11.2 — ``/v1/demo/*`` must be gated by ``settings.demo_enabled``."""

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
CONFIGS = REPO_ROOT / "configs"


def _build_settings(tmp_path: Path, *, demo_enabled: bool) -> Settings:
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
        log_level="WARNING",
        demo_enabled=demo_enabled,
    )


@pytest.fixture
def _client_factory(tmp_path: Path) -> Iterator[object]:
    def _make(*, demo_enabled: bool) -> TestClient:
        settings = _build_settings(tmp_path, demo_enabled=demo_enabled)
        algo = load_algo_params(settings.algo_params_version, base_dir=CONFIGS / "algo_params")
        app = create_app(
            settings=settings,
            algo_params=algo,
            left_calibration=load_calibration(settings.default_calibration_left),
            right_calibration=load_calibration(settings.default_calibration_right),
            session_repo=InMemorySessionRepository(),
            meas_repo=InMemoryMeasurementRepository(),
            chassis_repo=InMemoryChassisRepository(),
            blob_store=InMemoryBlobStore(),
            start_watchers=False,
            run_consumer=False,
        )
        return TestClient(app)

    yield _make


def test_demo_routes_absent_when_disabled(_client_factory) -> None:  # type: ignore[no-untyped-def]
    client: TestClient = _client_factory(demo_enabled=False)
    # GET paths fall through to the SPA fallback which now 404s on /v1/*.
    assert client.get("/v1/demo/replay/status").status_code == 404
    # POST paths return 405 (GET-only SPA fallback exists) OR 404 depending
    # on FastAPI version. Both mean "route not reachable" -- the contract is
    # that the demo surface is not mounted.
    assert client.post("/v1/demo/replay/start", json={}).status_code in (404, 405)
    assert client.post("/v1/demo/replay/stop", json={}).status_code in (404, 405)


def test_demo_routes_present_when_enabled(_client_factory) -> None:  # type: ignore[no-untyped-def]
    client: TestClient = _client_factory(demo_enabled=True)
    r = client.get("/v1/demo/replay/status")
    assert r.status_code == 200
    body = r.json()
    # The full ReplayStatus schema round-trips -- we just assert the
    # known keys so we catch drift.
    assert {"running", "source_dir", "interval_seconds", "pairs_sent", "total_pairs"} <= set(body)
