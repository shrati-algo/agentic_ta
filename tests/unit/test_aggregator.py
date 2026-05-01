"""Tests for tad.workers.aggregator — status matrix, asymmetry, orphan flush."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

import pytest

from tad.persistence.models import MeasurementRow
from tad.workers.aggregator import Aggregator, combine_status
from tests.fakes import InMemoryChassisRepository


def _meas(
    chassis_no: str,
    side: Literal["L", "R"],
    diameter: float | None,
    status: Literal["PASS", "REVIEW", "FAIL", "ERROR"],
    session_id: UUID,
) -> MeasurementRow:
    return MeasurementRow(
        measurement_id=uuid4(),
        session_id=session_id,
        chassis_no=chassis_no,
        camera_side=side,
        image_path=f"/tmp/{chassis_no}_{side}.jpg",
        diameter_mm=diameter,
        tolerance_min_mm=47.0,
        tolerance_max_mm=47.5,
        status=status,
        confidence_score=0.9 if status != "ERROR" else None,
        circle_center_x_px=100,
        circle_center_y_px=100,
        radius_px=diameter * 12.14 / 2 if diameter else None,
        mm_per_px=0.08234,
        calibration_version="cal-test-L" if side == "L" else "cal-test-R",
        algo_params_version="algo-1.3.0",
        debug_image_key=None,
        error_code=None if status != "ERROR" else "ERR_NO_CIRCLE",
        error_message=None,
        processed_at=datetime.now(UTC),
        latency_ms=100,
    )


class TestCombineStatus:
    @pytest.mark.parametrize(
        ("left", "right", "expected"),
        [
            ("PASS", "PASS", "PASS"),
            ("PASS", "REVIEW", "REVIEW"),
            ("PASS", "FAIL", "FAIL"),
            ("PASS", "ERROR", "ERROR"),
            ("REVIEW", "PASS", "REVIEW"),
            ("REVIEW", "REVIEW", "REVIEW"),
            ("REVIEW", "FAIL", "FAIL"),
            ("REVIEW", "ERROR", "ERROR"),
            ("FAIL", "PASS", "FAIL"),
            ("FAIL", "REVIEW", "FAIL"),
            ("FAIL", "FAIL", "FAIL"),
            ("FAIL", "ERROR", "FAIL"),
            ("ERROR", "PASS", "ERROR"),
            ("ERROR", "REVIEW", "ERROR"),
            ("ERROR", "FAIL", "FAIL"),
            ("ERROR", "ERROR", "ERROR"),
        ],
    )
    def test_all_matrix_cells(self, left: str, right: str, expected: str) -> None:
        result = combine_status(
            left,  # type: ignore[arg-type]
            right,  # type: ignore[arg-type]
            asymmetry_mm=None,
            asymmetry_threshold_mm=0.15,
        )
        assert result == expected

    def test_asymmetry_downgrade_on_pass(self) -> None:
        assert (
            combine_status("PASS", "PASS", asymmetry_mm=0.20, asymmetry_threshold_mm=0.15)
            == "REVIEW"
        )

    def test_asymmetry_preserves_review(self) -> None:
        assert (
            combine_status("PASS", "REVIEW", asymmetry_mm=0.30, asymmetry_threshold_mm=0.15)
            == "REVIEW"
        )

    def test_asymmetry_threshold_boundary(self) -> None:
        assert (
            combine_status("PASS", "PASS", asymmetry_mm=0.15, asymmetry_threshold_mm=0.15) == "PASS"
        )


class TestAggregator:
    async def test_emits_on_pair_complete(self) -> None:
        sid = uuid4()
        repo = InMemoryChassisRepository()
        emitted: list = []

        async def _emit(row):  # type: ignore[no-untyped-def]
            emitted.append(row)

        agg = Aggregator(session_id=sid, chassis_repo=repo, emit=_emit)
        await agg.accept(_meas("ABC12345678901234", "L", 47.25, "PASS", sid))
        assert emitted == []
        await agg.accept(_meas("ABC12345678901234", "R", 47.28, "PASS", sid))
        assert len(emitted) == 1
        row = emitted[0]
        assert row.overall_status == "PASS"
        assert row.left_diameter_mm == 47.25
        assert row.right_diameter_mm == 47.28
        assert abs(row.avg_diameter_mm - 47.265) < 1e-6
        assert abs(row.asymmetry_mm - 0.03) < 1e-6

    async def test_asymmetry_downgrades(self) -> None:
        sid = uuid4()
        repo = InMemoryChassisRepository()
        emitted: list = []

        async def _emit(row):  # type: ignore[no-untyped-def]
            emitted.append(row)

        agg = Aggregator(
            session_id=sid,
            chassis_repo=repo,
            emit=_emit,
            asymmetry_threshold_mm=0.10,
        )
        await agg.accept(_meas("ABC12345678901234", "L", 47.10, "PASS", sid))
        await agg.accept(_meas("ABC12345678901234", "R", 47.40, "PASS", sid))
        assert emitted[0].overall_status == "REVIEW"

    async def test_flush_emits_orphan_as_review(self) -> None:
        sid = uuid4()
        repo = InMemoryChassisRepository()
        emitted: list = []

        async def _emit(row):  # type: ignore[no-untyped-def]
            emitted.append(row)

        agg = Aggregator(session_id=sid, chassis_repo=repo, emit=_emit)
        await agg.accept(_meas("ABC12345678901234", "L", 47.25, "PASS", sid))
        rows = await agg.flush()
        assert len(rows) == 1
        assert rows[0].overall_status == "REVIEW"
        assert rows[0].reason == "missing side: R"
        assert rows[0].right_diameter_mm is None

    async def test_persists_via_repo(self) -> None:
        sid = uuid4()
        repo = InMemoryChassisRepository()

        async def _emit(row):  # type: ignore[no-untyped-def]
            pass

        agg = Aggregator(session_id=sid, chassis_repo=repo, emit=_emit)
        await agg.accept(_meas("ABC12345678901234", "L", 47.25, "PASS", sid))
        await agg.accept(_meas("ABC12345678901234", "R", 47.28, "PASS", sid))
        assert len(repo.rows) == 1
