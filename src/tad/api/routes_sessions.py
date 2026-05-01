"""Session-lifecycle and event-stream routes."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from tad.api.deps import get_measurement_repo, get_session_manager, get_session_repo
from tad.api.errors import SessionNotActiveError
from tad.api.schemas import (
    MeasurementResponse,
    SessionInfo,
    SessionSummary,
    StartRequest,
    StartResponse,
    StopResponse,
)
from tad.persistence.repositories import MeasurementRepository, SessionRepository
from tad.workers.manager import SessionManager

router = APIRouter(prefix="/v1/sessions", tags=["sessions"])


@router.post("/start", status_code=201, response_model=StartResponse)
async def start_session(
    body: StartRequest,
    mgr: SessionManager = Depends(get_session_manager),
) -> StartResponse:
    rt = await mgr.start(
        started_by=body.started_by, shift=body.shift, area=body.area, notes=body.notes
    )
    return StartResponse(
        session_id=rt.session.session_id,
        status="ACTIVE",
        left_dir=rt.session.left_dir,
        right_dir=rt.session.right_dir,
        algo_params_version=rt.algo_params.version,
        left_calibration=rt.calibrations["L"].calibration_id,
        right_calibration=rt.calibrations["R"].calibration_id,
        started_at=rt.session.started_at,
    )


@router.post("/{session_id}/stop", response_model=StopResponse)
async def stop_session(
    session_id: UUID,
    mgr: SessionManager = Depends(get_session_manager),
) -> StopResponse:
    result = await mgr.stop(session_id)
    summary_dict = result["summary"]
    summary = SessionSummary(
        **{
            "pass": summary_dict["pass"],
            "review": summary_dict["review"],
            "fail": summary_dict["fail"],
            "error": summary_dict["error"],
            "total": summary_dict["total"],
            "incomplete": summary_dict["incomplete"],
        }
    )
    return StopResponse(
        session_id=result["session_id"],
        status="STOPPED",
        stopped_at=result["stopped_at"],
        summary=summary,
    )


@router.get("", response_model=list[SessionInfo])
async def list_sessions(
    status: str | None = None,
    session_repo: SessionRepository = Depends(get_session_repo),
) -> list[SessionInfo]:
    if status == "ACTIVE":
        rows = await session_repo.list_active()
    else:
        rows = []
    return [
        SessionInfo(
            session_id=r.session_id,
            status=r.status,
            started_at=r.started_at,
            stopped_at=r.stopped_at,
            algo_params_version=r.algo_params_version,
        )
        for r in rows
    ]


def _default_json(value):  # type: ignore[no-untyped-def]
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


@router.get("/{session_id}/events")
async def session_events(
    session_id: UUID,
    request: Request,
    mgr: SessionManager = Depends(get_session_manager),
) -> EventSourceResponse:
    rt = mgr.require_active(session_id)
    queue = rt.broker.subscribe()

    async def _stream() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                except TimeoutError:
                    continue
                yield {
                    "event": event.type,
                    "data": json.dumps(event.payload, default=_default_json),
                }
                if event.type == "session_closed":
                    break
        finally:
            rt.broker.unsubscribe(queue)

    return EventSourceResponse(_stream())


@router.get("/{session_id}/results", response_model=list[MeasurementResponse])
async def session_results(
    session_id: UUID,
    since: datetime | None = None,
    meas_repo: MeasurementRepository = Depends(get_measurement_repo),
) -> list[MeasurementResponse]:
    rows = await meas_repo.list_by_session(session_id, since=since)
    return [
        MeasurementResponse(
            measurement_id=r.measurement_id,
            session_id=r.session_id,
            chassis_no=r.chassis_no,
            camera_side=r.camera_side,
            diameter_mm=r.diameter_mm,
            status=r.status,
            confidence_score=r.confidence_score,
            mm_per_px=r.mm_per_px,
            calibration_version=r.calibration_version,
            algo_params_version=r.algo_params_version,
            debug_image_url=f"/v1/debug/{r.measurement_id}" if r.debug_image_key else None,
            error_code=r.error_code,
            error_message=r.error_message,
            processed_at=r.processed_at,
            latency_ms=r.latency_ms,
        )
        for r in rows
    ]


# Re-export for tests that check the error type is reachable
__all__ = ["router", "SessionNotActiveError"]
