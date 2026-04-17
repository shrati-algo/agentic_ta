"""STORY-11.3 — ``ServiceTokenMiddleware`` behaviour.

- AUTH_ENABLED=false         -> middleware not installed, everything open
- AUTH_ENABLED=true + tokens -> missing/invalid token = 401; valid = 200
- AUTH_ENABLED=true + no tokens -> "allow all" (misconfig safety)
- Health, readiness, UI root -> always exempt
"""

from __future__ import annotations

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


def _build(
    tmp_path: Path,
    *,
    auth_enabled: bool,
    service_tokens: str = "",
) -> TestClient:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    settings = Settings(
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
        auth_enabled=auth_enabled,
        service_tokens=service_tokens,
        demo_enabled=False,
    )
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


def test_auth_off_is_wide_open(tmp_path: Path) -> None:
    client = _build(tmp_path, auth_enabled=False)
    # No token present, not an exempt path -- still 200 because auth is off.
    r = client.get("/v1/chassis?page=1&page_size=1")
    assert r.status_code == 200


def test_auth_on_missing_token_is_401(tmp_path: Path) -> None:
    client = _build(tmp_path, auth_enabled=True, service_tokens="tok-a,tok-b")
    r = client.get("/v1/chassis?page=1&page_size=1")
    assert r.status_code == 401
    body = r.json()
    assert body["error_code"] == "ERR_UNAUTHORIZED"


def test_auth_on_valid_token_is_200(tmp_path: Path) -> None:
    client = _build(tmp_path, auth_enabled=True, service_tokens="tok-a,tok-b")
    r = client.get(
        "/v1/chassis?page=1&page_size=1",
        headers={"X-Service-Token": "tok-b"},
    )
    assert r.status_code == 200


def test_health_and_ready_always_exempt(tmp_path: Path) -> None:
    client = _build(tmp_path, auth_enabled=True, service_tokens="tok-a")
    assert client.get("/v1/health").status_code == 200
    # /v1/ready can 503 if calibrations missing, but never 401.
    assert client.get("/v1/ready").status_code != 401


def test_misconfigured_auth_without_tokens_allows_all(tmp_path: Path) -> None:
    """If AUTH_ENABLED=true but SERVICE_TOKENS is empty, don't lock out the
    cluster -- the middleware short-circuits as "allow all"."""
    client = _build(tmp_path, auth_enabled=True, service_tokens="")
    r = client.get("/v1/chassis?page=1&page_size=1")
    assert r.status_code == 200


@pytest.mark.parametrize("bad", ["", "wrong", "tok-b "])
def test_auth_on_invalid_tokens_rejected(tmp_path: Path, bad: str) -> None:
    client = _build(tmp_path, auth_enabled=True, service_tokens="tok-a,tok-b")
    r = client.get(
        "/v1/chassis?page=1&page_size=1",
        headers={"X-Service-Token": bad},
    )
    assert r.status_code == 401
