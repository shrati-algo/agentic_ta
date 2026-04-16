"""FastAPI dependency wiring.

The app holds its stateful singletons (session manager, repositories,
blob store) on ``app.state``; these ``Depends(...)``-level functions
extract them typed.
"""

from __future__ import annotations

from fastapi import Request

from tad.persistence.blob_store import DebugImageStore
from tad.persistence.repositories import (
    ChassisRepository,
    MeasurementRepository,
    SessionRepository,
)
from tad.sessions.manager import SessionManager


def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager  # type: ignore[no-any-return]


def get_session_repo(request: Request) -> SessionRepository:
    return request.app.state.session_repo  # type: ignore[no-any-return]


def get_measurement_repo(request: Request) -> MeasurementRepository:
    return request.app.state.meas_repo  # type: ignore[no-any-return]


def get_chassis_repo(request: Request) -> ChassisRepository:
    return request.app.state.chassis_repo  # type: ignore[no-any-return]


def get_blob_store(request: Request) -> DebugImageStore:
    return request.app.state.blob_store  # type: ignore[no-any-return]
