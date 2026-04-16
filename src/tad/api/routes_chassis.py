"""Chassis list, detail, decision, and flag routes."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from tad.api.deps import get_chassis_repo, get_measurement_repo
from tad.api.errors import ChassisNotFoundError
from tad.api.schemas import (
    ChassisDetail,
    ChassisListItem,
    ChassisListResponse,
    ChassisPerCamera,
    DecisionRequest,
    FlagRequest,
)
from tad.persistence.repositories import ChassisRepository, MeasurementRepository

router = APIRouter(prefix="/v1/chassis", tags=["chassis"])


@router.get("", response_model=ChassisListResponse)
async def list_chassis(
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    status: str | None = None,
    shift: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 10,
    chassis_repo: ChassisRepository = Depends(get_chassis_repo),
) -> ChassisListResponse:
    rows, total = await chassis_repo.list_page(
        from_ts=from_ts,
        to_ts=to_ts,
        status=status,
        shift=shift,
        search=search,
        page=page,
        page_size=page_size,
    )
    items = [
        ChassisListItem(
            chassis_record_id=r.chassis_record_id,
            chassis_no=r.chassis_no,
            overall_status=r.overall_status,
            avg_diameter_mm=r.avg_diameter_mm,
            timestamp=r.aggregated_at,
            shift=r.shift,
            area=r.area,
            flagged=r.flagged,
        )
        for r in rows
    ]
    return ChassisListResponse(page=page, page_size=page_size, total=total, items=items)


@router.get("/{chassis_record_id}", response_model=ChassisDetail)
async def get_chassis(
    chassis_record_id: UUID,
    chassis_repo: ChassisRepository = Depends(get_chassis_repo),
    meas_repo: MeasurementRepository = Depends(get_measurement_repo),
) -> ChassisDetail:
    row = await chassis_repo.get(chassis_record_id)
    if row is None:
        raise ChassisNotFoundError(f"chassis_record not found: {chassis_record_id}")

    left_per = None
    right_per = None
    if row.left_measurement_id:
        m = await meas_repo.get(row.left_measurement_id)
        if m:
            left_per = ChassisPerCamera(
                measurement_id=m.measurement_id,
                diameter_mm=m.diameter_mm,
                status=m.status,
                confidence=m.confidence_score,
                debug_image_url=f"/v1/debug/{m.measurement_id}",
            )
    if row.right_measurement_id:
        m = await meas_repo.get(row.right_measurement_id)
        if m:
            right_per = ChassisPerCamera(
                measurement_id=m.measurement_id,
                diameter_mm=m.diameter_mm,
                status=m.status,
                confidence=m.confidence_score,
                debug_image_url=f"/v1/debug/{m.measurement_id}",
            )

    return ChassisDetail(
        chassis_record_id=row.chassis_record_id,
        chassis_no=row.chassis_no,
        overall_status=row.overall_status,
        flagged=row.flagged,
        timestamp=row.aggregated_at,
        shift=row.shift,
        area=row.area,
        left=left_per,
        right=right_per,
        operator_decision=row.operator_decision,
    )


@router.post("/{chassis_record_id}/decision", response_model=ChassisDetail)
async def record_decision(
    chassis_record_id: UUID,
    body: DecisionRequest,
    chassis_repo: ChassisRepository = Depends(get_chassis_repo),
    meas_repo: MeasurementRepository = Depends(get_measurement_repo),
) -> ChassisDetail:
    row = await chassis_repo.set_decision(
        chassis_record_id,
        decision=body.decision,
        decided_by=body.decided_by,
        decided_at=datetime.now(UTC),
    )
    if row is None:
        raise ChassisNotFoundError(f"chassis_record not found: {chassis_record_id}")
    return await get_chassis(chassis_record_id, chassis_repo, meas_repo)


@router.post("/{chassis_record_id}/flag", response_model=ChassisDetail)
async def flag_chassis(
    chassis_record_id: UUID,
    body: FlagRequest,
    chassis_repo: ChassisRepository = Depends(get_chassis_repo),
    meas_repo: MeasurementRepository = Depends(get_measurement_repo),
) -> ChassisDetail:
    row = await chassis_repo.set_flagged(chassis_record_id, flagged=body.flagged)
    if row is None:
        raise ChassisNotFoundError(f"chassis_record not found: {chassis_record_id}")
    return await get_chassis(chassis_record_id, chassis_repo, meas_repo)
