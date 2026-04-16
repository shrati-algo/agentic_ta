"""Individual measurement + debug-image streaming routes."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from tad.api.deps import get_blob_store, get_measurement_repo
from tad.api.errors import MeasurementNotFoundError
from tad.api.schemas import MeasurementResponse
from tad.persistence.blob_store import DebugImageStore
from tad.persistence.repositories import MeasurementRepository

router = APIRouter(prefix="/v1", tags=["measurements"])


@router.get("/measurements/{measurement_id}", response_model=MeasurementResponse)
async def get_measurement(
    measurement_id: UUID,
    meas_repo: MeasurementRepository = Depends(get_measurement_repo),
) -> MeasurementResponse:
    row = await meas_repo.get(measurement_id)
    if row is None:
        raise MeasurementNotFoundError(f"measurement not found: {measurement_id}")
    return MeasurementResponse(
        measurement_id=row.measurement_id,
        session_id=row.session_id,
        chassis_no=row.chassis_no,
        camera_side=row.camera_side,
        diameter_mm=row.diameter_mm,
        status=row.status,
        confidence_score=row.confidence_score,
        mm_per_px=row.mm_per_px,
        calibration_version=row.calibration_version,
        algo_params_version=row.algo_params_version,
        debug_image_url=f"/v1/debug/{row.measurement_id}" if row.debug_image_key else None,
        error_code=row.error_code,
        error_message=row.error_message,
        processed_at=row.processed_at,
        latency_ms=row.latency_ms,
    )


@router.get("/debug/{measurement_id}")
async def get_debug_image(
    measurement_id: UUID,
    meas_repo: MeasurementRepository = Depends(get_measurement_repo),
    blob_store: DebugImageStore = Depends(get_blob_store),
) -> StreamingResponse:
    row = await meas_repo.get(measurement_id)
    if row is None or row.debug_image_key is None:
        raise MeasurementNotFoundError(f"debug image not found for {measurement_id}")
    iterator = await blob_store.stream(row.debug_image_key)
    return StreamingResponse(iterator, media_type="image/jpeg")
