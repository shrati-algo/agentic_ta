"""In-memory fakes for the persistence protocols.

Used by unit + integration tests that do not need a real Postgres.
They satisfy the same method signatures as ``SqlSessionRepository`` &
friends.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from tad.persistence.models import ChassisRow, MeasurementRow, SessionRow


class InMemorySessionRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, SessionRow] = {}

    async def create(self, row: SessionRow) -> SessionRow:
        self.rows[row.session_id] = row
        return row

    async def mark_stopped(
        self, session_id: UUID, stopped_at: datetime, summary: dict[str, Any]
    ) -> None:
        cur = self.rows.get(session_id)
        if cur is None:
            return
        updated = SessionRow(
            **{
                **cur.__dict__,
                "stopped_at": stopped_at,
                "status": "STOPPED",
                "summary_json": summary,
            }
        )
        self.rows[session_id] = updated

    async def get(self, session_id: UUID) -> SessionRow | None:
        return self.rows.get(session_id)

    async def list_active(self) -> list[SessionRow]:
        return [r for r in self.rows.values() if r.status == "ACTIVE"]


class InMemoryMeasurementRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, MeasurementRow] = {}

    async def insert(self, row: MeasurementRow) -> MeasurementRow:
        self.rows[row.measurement_id] = row
        return row

    async def get(self, measurement_id: UUID) -> MeasurementRow | None:
        return self.rows.get(measurement_id)

    async def list_by_session(
        self, session_id: UUID, *, since: datetime | None = None
    ) -> list[MeasurementRow]:
        out = [r for r in self.rows.values() if r.session_id == session_id]
        if since is not None:
            out = [r for r in out if r.processed_at >= since]
        return sorted(out, key=lambda r: r.processed_at)

    async def get_pair(
        self, session_id: UUID, chassis_no: str
    ) -> tuple[MeasurementRow | None, MeasurementRow | None]:
        cand = [
            r
            for r in self.rows.values()
            if r.session_id == session_id and r.chassis_no == chassis_no
        ]
        left = next((r for r in cand if r.camera_side == "L"), None)
        right = next((r for r in cand if r.camera_side == "R"), None)
        return left, right


class InMemoryChassisRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, ChassisRow] = {}

    async def upsert(self, row: ChassisRow) -> ChassisRow:
        # Dedup by (session_id, chassis_no) like the real unique constraint
        existing = next(
            (
                r
                for r in self.rows.values()
                if r.session_id == row.session_id and r.chassis_no == row.chassis_no
            ),
            None,
        )
        if existing is not None:
            # Replace fields but keep the existing chassis_record_id
            merged = ChassisRow(**{**row.__dict__, "chassis_record_id": existing.chassis_record_id})
            self.rows[existing.chassis_record_id] = merged
            return merged
        self.rows[row.chassis_record_id] = row
        return row

    async def get(self, chassis_record_id: UUID) -> ChassisRow | None:
        return self.rows.get(chassis_record_id)

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
        rows = list(self.rows.values())
        if from_ts is not None:
            rows = [r for r in rows if r.aggregated_at >= from_ts]
        if to_ts is not None:
            rows = [r for r in rows if r.aggregated_at <= to_ts]
        if status is not None:
            rows = [r for r in rows if r.overall_status == status]
        if shift is not None:
            rows = [r for r in rows if r.shift == shift]
        if search is not None:
            rows = [r for r in rows if r.chassis_no.startswith(search)]
        rows.sort(key=lambda r: r.aggregated_at, reverse=True)
        total = len(rows)
        start = (page - 1) * page_size
        return rows[start : start + page_size], total

    async def search_by_no(self, chassis_no: str) -> list[ChassisRow]:
        return [r for r in self.rows.values() if r.chassis_no == chassis_no]

    async def set_decision(
        self,
        chassis_record_id: UUID,
        decision: str,
        decided_by: str,
        decided_at: datetime,
    ) -> ChassisRow | None:
        cur = self.rows.get(chassis_record_id)
        if cur is None:
            return None
        updated = ChassisRow(
            **{
                **cur.__dict__,
                "operator_decision": decision,
                "decided_by": decided_by,
                "decided_at": decided_at,
            }
        )
        self.rows[chassis_record_id] = updated
        return updated

    async def set_flagged(self, chassis_record_id: UUID, flagged: bool) -> ChassisRow | None:
        cur = self.rows.get(chassis_record_id)
        if cur is None:
            return None
        updated = ChassisRow(**{**cur.__dict__, "flagged": flagged})
        self.rows[chassis_record_id] = updated
        return updated
