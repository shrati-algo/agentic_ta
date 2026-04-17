"""Uvicorn entrypoint for the Trailing Arm Detection service.

Production wiring: SQL-backed repositories, MinIO-backed blob store.
Tests use ``tad.api.app.create_app`` directly with in-memory fakes.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI

from tad.api.app import create_app
from tad.config.algo_params import load_algo_params
from tad.config.settings import Settings, get_settings
from tad.persistence.blob_store import DebugImageStore, InMemoryBlobStore, MinIOStore
from tad.persistence.db import build_engine, build_session_factory
from tad.persistence.repositories import (
    SqlChassisRepository,
    SqlMeasurementRepository,
    SqlSessionRepository,
)

_log = logging.getLogger(__name__)


def _ensure_image_dirs(settings: Settings) -> None:
    """Create the watched folders so ``SessionManager.start()`` does not
    immediately raise ``FolderUnavailableError`` on a fresh container.
    """
    Path(settings.images_left_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.images_right_dir).mkdir(parents=True, exist_ok=True)


def _build_blob_store(settings: Settings) -> DebugImageStore:
    """Prefer MinIO; fall back to in-memory if it is unreachable.

    The MinIO client's constructor does a ``bucket_exists`` probe that
    fails fast when the endpoint is wrong or MinIO is still booting.
    The InMemoryBlobStore is a last-resort so a network blip during
    boot does not crash the app; production deployments should have a
    reachable MinIO at all times.
    """
    try:
        return MinIOStore(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
        )
    except Exception as exc:  # noqa: BLE001 -- last-resort downgrade
        _log.warning("MinIO unreachable (%s); using InMemoryBlobStore", exc)
        return InMemoryBlobStore()


def _default_app() -> FastAPI:
    settings = get_settings()
    _ensure_image_dirs(settings)

    engine = build_engine(settings.db_dsn)
    factory = build_session_factory(engine)
    session_repo = SqlSessionRepository(factory)
    meas_repo = SqlMeasurementRepository(factory)
    chassis_repo = SqlChassisRepository(factory)

    # When the deployment runs the demo replay (yca_valid fixtures)
    # we widen the PASS / REVIEW / FAIL bands so the dashboard shows
    # a useful mix of outcomes. Production sites with a real caliper
    # rig should leave demo_enabled=False and the stock algo-1.3.0
    # bands take effect untouched.
    algo_params = load_algo_params(settings.algo_params_version)
    if settings.demo_enabled:
        algo_params = algo_params.model_copy(
            update={
                "target": algo_params.target.model_copy(
                    update={"diameter_mm": 20.0, "radius_tolerance_mm": 2.0}
                ),
                "tolerance": algo_params.tolerance.model_copy(
                    update={
                        "min_mm": 15.0,
                        "max_mm": 25.0,
                        "ok_band_mm": 1.0,
                        "somewhat_ok_band_mm": 1.5,
                        "asymmetry_threshold_mm": 2.5,
                    }
                ),
                "hough": algo_params.hough.model_copy(update={"param2": 15}),
            }
        )

    return create_app(
        settings=settings,
        algo_params=algo_params,
        session_repo=session_repo,
        meas_repo=meas_repo,
        chassis_repo=chassis_repo,
        blob_store=_build_blob_store(settings),
        start_watchers=True,
    )


app: FastAPI = _default_app()
