"""Chassis aggregator — joins per-camera results into chassis results.

One instance per active session.  Holds an in-memory ``pending`` map
keyed by ``chassis_no``; when both sides arrive, emits a chassis result,
persists a ``ChassisRow``, and pops the entry.

Status matrix (TRD 7.1) is implemented in :func:`combine_status`; the
``somewhat_ok_band_mm`` downgrade is driven by the session's
``asymmetry_threshold_mm``.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from tad.persistence.models import ChassisRow, MeasurementRow
from tad.persistence.repositories import ChassisRepository

Status = Literal["PASS", "FAIL", "REVIEW", "ERROR"]

_MATRIX: dict[tuple[Status, Status], Status] = {
    ("PASS", "PASS"): "PASS",
    ("PASS", "REVIEW"): "REVIEW",
    ("PASS", "FAIL"): "FAIL",
    ("PASS", "ERROR"): "ERROR",
    ("REVIEW", "PASS"): "REVIEW",
    ("REVIEW", "REVIEW"): "REVIEW",
    ("REVIEW", "FAIL"): "FAIL",
    ("REVIEW", "ERROR"): "ERROR",
    ("FAIL", "PASS"): "FAIL",
    ("FAIL", "REVIEW"): "FAIL",
    ("FAIL", "FAIL"): "FAIL",
    ("FAIL", "ERROR"): "FAIL",
    ("ERROR", "PASS"): "ERROR",
    ("ERROR", "REVIEW"): "ERROR",
    ("ERROR", "FAIL"): "FAIL",
    ("ERROR", "ERROR"): "ERROR",
}


def combine_status(
    left: Status,
    right: Status,
    asymmetry_mm: float | None,
    asymmetry_threshold_mm: float,
) -> Status:
    """Apply TRD 7.1 matrix plus the asymmetry downgrade."""
    overall = _MATRIX[(left, right)]
    if overall == "PASS" and asymmetry_mm is not None and asymmetry_mm > asymmetry_threshold_mm:
        return "REVIEW"
    return overall


# Callback invoked once a chassis result is ready.  Receives the row.
ChassisEmitter = Callable[[ChassisRow], Awaitable[None]]


class Aggregator:
    def __init__(
        self,
        session_id: UUID,
        chassis_repo: ChassisRepository,
        emit: ChassisEmitter,
        *,
        asymmetry_threshold_mm: float = 0.15,
        shift: str | None = None,
        area: str | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_id = session_id
        self._chassis_repo = chassis_repo
        self._emit = emit
        self._asymmetry_threshold_mm = asymmetry_threshold_mm
        self._shift = shift
        self._area = area
        self._clock = clock
        self._pending: dict[str, dict[str, MeasurementRow]] = {}
        self._lock = asyncio.Lock()

    async def accept(self, measurement: MeasurementRow) -> None:
        async with self._lock:
            pair = self._pending.setdefault(measurement.chassis_no, {})
            pair[measurement.camera_side] = measurement
            if "L" in pair and "R" in pair:
                left = pair["L"]
                right = pair["R"]
                row = self._build_row(left=left, right=right, reason=None)
                self._pending.pop(measurement.chassis_no, None)
                await self._chassis_repo.upsert(row)
                await self._emit(row)

    async def flush(self) -> list[ChassisRow]:
        async with self._lock:
            emitted: list[ChassisRow] = []
            for _chassis_no, pair in list(self._pending.items()):
                left = pair.get("L")
                right = pair.get("R")
                missing = "R" if left is not None and right is None else "L"
                reason = f"missing side: {missing}"
                row = self._build_row(left=left, right=right, reason=reason)
                # Orphan chassis -> REVIEW (TRD 7.2) unless already ERROR
                if row.overall_status != "ERROR":
                    row = ChassisRow(**{**row.__dict__, "overall_status": "REVIEW"})
                await self._chassis_repo.upsert(row)
                await self._emit(row)
                emitted.append(row)
            self._pending.clear()
            return emitted

    def _build_row(
        self,
        *,
        left: MeasurementRow | None,
        right: MeasurementRow | None,
        reason: str | None,
    ) -> ChassisRow:
        l_d = left.diameter_mm if left else None
        r_d = right.diameter_mm if right else None
        avg = (l_d + r_d) / 2.0 if l_d is not None and r_d is not None else None
        asym = abs(l_d - r_d) if l_d is not None and r_d is not None else None

        if left is not None and right is not None:
            overall: Status = combine_status(
                left.status, right.status, asym, self._asymmetry_threshold_mm
            )
        elif left is not None:
            overall = left.status
        elif right is not None:
            overall = right.status
        else:
            overall = "ERROR"

        any_side = left or right
        chassis_no = any_side.chassis_no if any_side is not None else ""

        return ChassisRow(
            chassis_record_id=uuid4(),
            session_id=self._session_id,
            chassis_no=chassis_no,
            left_measurement_id=left.measurement_id if left else None,
            right_measurement_id=right.measurement_id if right else None,
            left_diameter_mm=l_d,
            right_diameter_mm=r_d,
            avg_diameter_mm=avg,
            asymmetry_mm=asym,
            overall_status=overall,
            reason=reason,
            aggregated_at=self._clock(),
            operator_decision=None,
            decided_by=None,
            decided_at=None,
            flagged=False,
            shift=self._shift,
            area=self._area,
        )
