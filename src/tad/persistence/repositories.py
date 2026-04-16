"""Repository protocols and their SQLAlchemy implementations.

The protocols are what the rest of the service depends on; tests swap in
in-memory fakes that satisfy the same shapes.  All methods are async.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tad.persistence.models import (
    ChassisRecordORM,
    ChassisRow,
    MeasurementORM,
    MeasurementRow,
    SessionORM,
    SessionRow,
)

# ---------------------------------------------------------------------------
# Protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class SessionRepository(Protocol):
    async def create(self, row: SessionRow) -> SessionRow: ...
    async def mark_stopped(
        self, session_id: UUID, stopped_at: datetime, summary: dict[str, Any]
    ) -> None: ...
    async def get(self, session_id: UUID) -> SessionRow | None: ...
    async def list_active(self) -> list[SessionRow]: ...


@runtime_checkable
class MeasurementRepository(Protocol):
    async def insert(self, row: MeasurementRow) -> MeasurementRow: ...
    async def get(self, measurement_id: UUID) -> MeasurementRow | None: ...
    async def list_by_session(
        self, session_id: UUID, *, since: datetime | None = None
    ) -> list[MeasurementRow]: ...
    async def get_pair(
        self, session_id: UUID, chassis_no: str
    ) -> tuple[MeasurementRow | None, MeasurementRow | None]: ...


@runtime_checkable
class ChassisRepository(Protocol):
    async def upsert(self, row: ChassisRow) -> ChassisRow: ...
    async def get(self, chassis_record_id: UUID) -> ChassisRow | None: ...
    async def list_page(
        self,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        status: str | None = None,
        shift: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[ChassisRow], int]: ...
    async def search_by_no(self, chassis_no: str) -> list[ChassisRow]: ...
    async def set_decision(
        self,
        chassis_record_id: UUID,
        decision: str,
        decided_by: str,
        decided_at: datetime,
    ) -> ChassisRow | None: ...
    async def set_flagged(self, chassis_record_id: UUID, flagged: bool) -> ChassisRow | None: ...


# ---------------------------------------------------------------------------
# SQLAlchemy implementations
# ---------------------------------------------------------------------------


def _session_row_from_orm(o: SessionORM) -> SessionRow:
    return SessionRow(
        session_id=o.session_id,
        started_at=o.started_at,
        stopped_at=o.stopped_at,
        started_by=o.started_by,
        status=o.status,  # type: ignore[arg-type]
        left_dir=o.left_dir,
        right_dir=o.right_dir,
        algo_params_version=o.algo_params_version,
        shift=o.shift,
        area=o.area,
        notes=o.notes,
        summary_json=o.summary_json,
    )


def _meas_row_from_orm(o: MeasurementORM) -> MeasurementRow:
    return MeasurementRow(
        measurement_id=o.measurement_id,
        session_id=o.session_id,
        chassis_no=o.chassis_no,
        camera_side=o.camera_side,  # type: ignore[arg-type]
        image_path=o.image_path,
        diameter_mm=float(o.diameter_mm) if o.diameter_mm is not None else None,
        tolerance_min_mm=float(o.tolerance_min_mm),
        tolerance_max_mm=float(o.tolerance_max_mm),
        status=o.status,  # type: ignore[arg-type]
        confidence_score=float(o.confidence_score) if o.confidence_score is not None else None,
        circle_center_x_px=o.circle_center_x_px,
        circle_center_y_px=o.circle_center_y_px,
        radius_px=float(o.radius_px) if o.radius_px is not None else None,
        mm_per_px=float(o.mm_per_px),
        calibration_version=o.calibration_version,
        algo_params_version=o.algo_params_version,
        debug_image_key=o.debug_image_key,
        error_code=o.error_code,
        error_message=o.error_message,
        processed_at=o.processed_at,
        latency_ms=o.latency_ms,
    )


def _chassis_row_from_orm(o: ChassisRecordORM) -> ChassisRow:
    return ChassisRow(
        chassis_record_id=o.chassis_record_id,
        session_id=o.session_id,
        chassis_no=o.chassis_no,
        left_measurement_id=o.left_measurement_id,
        right_measurement_id=o.right_measurement_id,
        left_diameter_mm=float(o.left_diameter_mm) if o.left_diameter_mm is not None else None,
        right_diameter_mm=float(o.right_diameter_mm) if o.right_diameter_mm is not None else None,
        avg_diameter_mm=float(o.avg_diameter_mm) if o.avg_diameter_mm is not None else None,
        asymmetry_mm=float(o.asymmetry_mm) if o.asymmetry_mm is not None else None,
        overall_status=o.overall_status,  # type: ignore[arg-type]
        reason=o.reason,
        aggregated_at=o.aggregated_at,
        operator_decision=o.operator_decision,  # type: ignore[arg-type]
        decided_by=o.decided_by,
        decided_at=o.decided_at,
        flagged=o.flagged,
        shift=o.shift,
        area=o.area,
    )


class SqlSessionRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def create(self, row: SessionRow) -> SessionRow:
        async with self._factory() as db:
            orm = SessionORM(
                session_id=row.session_id,
                started_at=row.started_at,
                stopped_at=row.stopped_at,
                started_by=row.started_by,
                status=row.status,
                left_dir=row.left_dir,
                right_dir=row.right_dir,
                algo_params_version=row.algo_params_version,
                shift=row.shift,
                area=row.area,
                notes=row.notes,
                summary_json=row.summary_json,
            )
            db.add(orm)
            await db.commit()
        return row

    async def mark_stopped(
        self, session_id: UUID, stopped_at: datetime, summary: dict[str, Any]
    ) -> None:
        async with self._factory() as db:
            await db.execute(
                update(SessionORM)
                .where(SessionORM.session_id == session_id)
                .values(stopped_at=stopped_at, status="STOPPED", summary_json=summary)
            )
            await db.commit()

    async def get(self, session_id: UUID) -> SessionRow | None:
        async with self._factory() as db:
            orm = await db.get(SessionORM, session_id)
            return _session_row_from_orm(orm) if orm else None

    async def list_active(self) -> list[SessionRow]:
        async with self._factory() as db:
            rows = (
                (await db.execute(select(SessionORM).where(SessionORM.status == "ACTIVE")))
                .scalars()
                .all()
            )
            return [_session_row_from_orm(r) for r in rows]


class SqlMeasurementRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def insert(self, row: MeasurementRow) -> MeasurementRow:
        async with self._factory() as db:
            db.add(
                MeasurementORM(
                    measurement_id=row.measurement_id,
                    session_id=row.session_id,
                    chassis_no=row.chassis_no,
                    camera_side=row.camera_side,
                    image_path=row.image_path,
                    diameter_mm=row.diameter_mm,
                    tolerance_min_mm=row.tolerance_min_mm,
                    tolerance_max_mm=row.tolerance_max_mm,
                    status=row.status,
                    confidence_score=row.confidence_score,
                    circle_center_x_px=row.circle_center_x_px,
                    circle_center_y_px=row.circle_center_y_px,
                    radius_px=row.radius_px,
                    mm_per_px=row.mm_per_px,
                    calibration_version=row.calibration_version,
                    algo_params_version=row.algo_params_version,
                    debug_image_key=row.debug_image_key,
                    error_code=row.error_code,
                    error_message=row.error_message,
                    processed_at=row.processed_at,
                    latency_ms=row.latency_ms,
                )
            )
            await db.commit()
        return row

    async def get(self, measurement_id: UUID) -> MeasurementRow | None:
        async with self._factory() as db:
            orm = await db.get(MeasurementORM, measurement_id)
            return _meas_row_from_orm(orm) if orm else None

    async def list_by_session(
        self, session_id: UUID, *, since: datetime | None = None
    ) -> list[MeasurementRow]:
        async with self._factory() as db:
            stmt = select(MeasurementORM).where(MeasurementORM.session_id == session_id)
            if since is not None:
                stmt = stmt.where(MeasurementORM.processed_at >= since)
            stmt = stmt.order_by(MeasurementORM.processed_at)
            rows = (await db.execute(stmt)).scalars().all()
            return [_meas_row_from_orm(r) for r in rows]

    async def get_pair(
        self, session_id: UUID, chassis_no: str
    ) -> tuple[MeasurementRow | None, MeasurementRow | None]:
        async with self._factory() as db:
            stmt = select(MeasurementORM).where(
                MeasurementORM.session_id == session_id,
                MeasurementORM.chassis_no == chassis_no,
            )
            rows = (await db.execute(stmt)).scalars().all()
            left = next((r for r in rows if r.camera_side == "L"), None)
            right = next((r for r in rows if r.camera_side == "R"), None)
            return (
                _meas_row_from_orm(left) if left else None,
                _meas_row_from_orm(right) if right else None,
            )


class SqlChassisRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    async def upsert(self, row: ChassisRow) -> ChassisRow:
        async with self._factory() as db:
            stmt = pg_insert(ChassisRecordORM).values(
                chassis_record_id=row.chassis_record_id,
                session_id=row.session_id,
                chassis_no=row.chassis_no,
                left_measurement_id=row.left_measurement_id,
                right_measurement_id=row.right_measurement_id,
                left_diameter_mm=row.left_diameter_mm,
                right_diameter_mm=row.right_diameter_mm,
                avg_diameter_mm=row.avg_diameter_mm,
                asymmetry_mm=row.asymmetry_mm,
                overall_status=row.overall_status,
                reason=row.reason,
                operator_decision=row.operator_decision,
                decided_by=row.decided_by,
                decided_at=row.decided_at,
                flagged=row.flagged,
                shift=row.shift,
                area=row.area,
                aggregated_at=row.aggregated_at,
            )
            update_cols = {
                c.name: c
                for c in stmt.excluded
                if c.name not in ("chassis_record_id", "session_id", "chassis_no")
            }
            stmt = stmt.on_conflict_do_update(
                constraint="uq_session_chassis",
                set_=update_cols,
            )
            await db.execute(stmt)
            await db.commit()
        return row

    async def get(self, chassis_record_id: UUID) -> ChassisRow | None:
        async with self._factory() as db:
            orm = await db.get(ChassisRecordORM, chassis_record_id)
            return _chassis_row_from_orm(orm) if orm else None

    async def list_page(
        self,
        *,
        from_ts: datetime | None = None,
        to_ts: datetime | None = None,
        status: str | None = None,
        shift: str | None = None,
        search: str | None = None,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[ChassisRow], int]:
        async with self._factory() as db:
            stmt = select(ChassisRecordORM)
            if from_ts is not None:
                stmt = stmt.where(ChassisRecordORM.aggregated_at >= from_ts)
            if to_ts is not None:
                stmt = stmt.where(ChassisRecordORM.aggregated_at <= to_ts)
            if status is not None:
                stmt = stmt.where(ChassisRecordORM.overall_status == status)
            if shift is not None:
                stmt = stmt.where(ChassisRecordORM.shift == shift)
            if search is not None:
                stmt = stmt.where(ChassisRecordORM.chassis_no.like(f"{search}%"))
            stmt = stmt.order_by(ChassisRecordORM.aggregated_at.desc())

            # Count (separate query for total)
            total_stmt = select(ChassisRecordORM.chassis_record_id)
            if from_ts is not None:
                total_stmt = total_stmt.where(ChassisRecordORM.aggregated_at >= from_ts)
            if to_ts is not None:
                total_stmt = total_stmt.where(ChassisRecordORM.aggregated_at <= to_ts)
            if status is not None:
                total_stmt = total_stmt.where(ChassisRecordORM.overall_status == status)
            if shift is not None:
                total_stmt = total_stmt.where(ChassisRecordORM.shift == shift)
            if search is not None:
                total_stmt = total_stmt.where(ChassisRecordORM.chassis_no.like(f"{search}%"))
            total = len((await db.execute(total_stmt)).scalars().all())

            stmt = stmt.offset((page - 1) * page_size).limit(page_size)
            rows = (await db.execute(stmt)).scalars().all()
            return [_chassis_row_from_orm(r) for r in rows], total

    async def search_by_no(self, chassis_no: str) -> list[ChassisRow]:
        async with self._factory() as db:
            rows = (
                (
                    await db.execute(
                        select(ChassisRecordORM).where(ChassisRecordORM.chassis_no == chassis_no)
                    )
                )
                .scalars()
                .all()
            )
            return [_chassis_row_from_orm(r) for r in rows]

    async def set_decision(
        self,
        chassis_record_id: UUID,
        decision: str,
        decided_by: str,
        decided_at: datetime,
    ) -> ChassisRow | None:
        async with self._factory() as db:
            await db.execute(
                update(ChassisRecordORM)
                .where(ChassisRecordORM.chassis_record_id == chassis_record_id)
                .values(operator_decision=decision, decided_by=decided_by, decided_at=decided_at)
            )
            await db.commit()
            orm = await db.get(ChassisRecordORM, chassis_record_id)
            return _chassis_row_from_orm(orm) if orm else None

    async def set_flagged(self, chassis_record_id: UUID, flagged: bool) -> ChassisRow | None:
        async with self._factory() as db:
            await db.execute(
                update(ChassisRecordORM)
                .where(ChassisRecordORM.chassis_record_id == chassis_record_id)
                .values(flagged=flagged)
            )
            await db.commit()
            orm = await db.get(ChassisRecordORM, chassis_record_id)
            return _chassis_row_from_orm(orm) if orm else None
