"""Uvicorn entrypoint for the Trailing Arm Detection service.

Production wiring: SQL-backed repositories, MinIO-backed blob store.
Tests use ``tad.api.app.create_app`` directly with in-memory fakes.
"""

from __future__ import annotations

from fastapi import FastAPI

from tad.api.app import create_app
from tad.config.settings import get_settings
from tad.persistence.blob_store import DebugImageStore, InMemoryBlobStore, MinIOStore
from tad.persistence.db import build_engine, build_session_factory
from tad.persistence.repositories import (
    SqlChassisRepository,
    SqlMeasurementRepository,
    SqlSessionRepository,
)


def _default_app() -> FastAPI:
    settings = get_settings()
    engine = build_engine(settings.db_dsn)
    factory = build_session_factory(engine)
    session_repo = SqlSessionRepository(factory)
    meas_repo = SqlMeasurementRepository(factory)
    chassis_repo = SqlChassisRepository(factory)
    blob_store: DebugImageStore
    try:
        blob_store = MinIOStore(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
        )
    except Exception:
        blob_store = InMemoryBlobStore()

    return create_app(
        settings=settings,
        session_repo=session_repo,
        meas_repo=meas_repo,
        chassis_repo=chassis_repo,
        blob_store=blob_store,
        start_watchers=True,
    )


app: FastAPI = _default_app()
