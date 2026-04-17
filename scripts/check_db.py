"""End-to-end backend <-> Postgres connectivity check.

Exercises the *real* async SQL repositories (no in-memory fakes) against
the running Postgres to prove the full persistence stack is wired
correctly.

What it does:
    1. Reads DB_DSN from the environment.
    2. Opens an async SQLAlchemy engine + session factory.
    3. Lists every table in the public schema and its row count.
    4. Inserts one SessionRow, one MeasurementRow, one ChassisRow via
       the production Sql* repositories.
    5. Reads each row back through the same repositories.
    6. Re-prints row counts so you can see the deltas.

By default the script leaves the rows in place so you can inspect them
with psql afterwards. Pass ``--cleanup`` to delete them before exit.

    # From the tad-app container (see README for env wiring):
    docker compose exec \\
        -e DB_DSN='postgresql+psycopg://tad:tad@postgres:5432/tad' \\
        ... tad python scripts/check_db.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import text  # noqa: E402

from tad.persistence.db import build_engine, build_session_factory  # noqa: E402
from tad.persistence.models import ChassisRow, MeasurementRow, SessionRow  # noqa: E402
from tad.persistence.repositories import (  # noqa: E402
    SqlChassisRepository,
    SqlMeasurementRepository,
    SqlSessionRepository,
)

_TABLES = ["sessions", "measurements", "chassis_records", "calibrations"]


async def _row_counts(factory) -> dict[str, int]:  # type: ignore[no-untyped-def]
    async with factory() as session:
        result: dict[str, int] = {}
        for name in _TABLES:
            row = (await session.execute(text(f"SELECT count(*) FROM {name}"))).scalar_one()
            result[name] = int(row)
        return result


def _print_counts(title: str, counts: dict[str, int]) -> None:
    print(f"  {title}")
    for name, n in counts.items():
        print(f"    {name:20s}  {n:>6d}")


async def _roundtrip(factory, *, cleanup: bool) -> None:  # type: ignore[no-untyped-def]
    session_repo = SqlSessionRepository(factory)
    meas_repo = SqlMeasurementRepository(factory)
    chassis_repo = SqlChassisRepository(factory)

    now = datetime.now(UTC)
    session_id = uuid4()
    measurement_id = uuid4()
    chassis_record_id = uuid4()
    chassis_no = "CHECKDBAAAAAAAAAA"  # 17 chars, VIN-safe

    # 1) Session
    created_session = await session_repo.create(
        SessionRow(
            session_id=session_id,
            started_at=now,
            stopped_at=None,
            started_by="check_db.py",
            status="ACTIVE",
            left_dir="/tmp/left",
            right_dir="/tmp/right",
            algo_params_version="algo-1.3.0",
            shift="A",
            area="Welding",
            notes="connectivity probe",
        )
    )
    fetched_session = await session_repo.get(session_id)
    assert fetched_session is not None and fetched_session.started_by == "check_db.py"

    # 2) Measurement
    created_meas = await meas_repo.insert(
        MeasurementRow(
            measurement_id=measurement_id,
            session_id=session_id,
            chassis_no=chassis_no,
            camera_side="L",
            image_path="/tmp/left/probe_L.jpg",
            diameter_mm=20.12,
            tolerance_min_mm=15.0,
            tolerance_max_mm=25.0,
            status="PASS",
            confidence_score=0.87,
            circle_center_x_px=1024,
            circle_center_y_px=768,
            radius_px=123.45,
            mm_per_px=0.0817,
            calibration_version="cal-2026-03-14-L",
            algo_params_version="algo-1.3.0",
            debug_image_key=None,
            error_code=None,
            error_message=None,
            processed_at=now,
            latency_ms=123,
        )
    )
    fetched_meas = await meas_repo.get(measurement_id)
    assert fetched_meas is not None and fetched_meas.diameter_mm == 20.12

    # 3) Chassis
    created_chassis = await chassis_repo.upsert(
        ChassisRow(
            chassis_record_id=chassis_record_id,
            session_id=session_id,
            chassis_no=chassis_no,
            left_measurement_id=measurement_id,
            right_measurement_id=None,
            left_diameter_mm=20.12,
            right_diameter_mm=None,
            avg_diameter_mm=20.12,
            asymmetry_mm=None,
            overall_status="PASS",
            reason=None,
            aggregated_at=now,
            flagged=False,
            shift="A",
            area="Welding",
        )
    )
    fetched_chassis = await chassis_repo.get(chassis_record_id)
    assert fetched_chassis is not None and fetched_chassis.overall_status == "PASS"

    print("  round-trip OK")
    print(f"    session_id         = {created_session.session_id}")
    print(f"    measurement_id     = {created_meas.measurement_id}  d={created_meas.diameter_mm} mm")
    print(
        f"    chassis_record_id  = {created_chassis.chassis_record_id}  "
        f"chassis_no={created_chassis.chassis_no}"
    )

    if cleanup:
        async with factory() as session:
            await session.execute(
                text("DELETE FROM chassis_records WHERE chassis_record_id = :i"),
                {"i": str(chassis_record_id)},
            )
            await session.execute(
                text("DELETE FROM measurements WHERE measurement_id = :i"),
                {"i": str(measurement_id)},
            )
            await session.execute(
                text("DELETE FROM sessions WHERE session_id = :i"),
                {"i": str(session_id)},
            )
            await session.commit()
        print("  probe rows deleted (--cleanup)")


async def _amain(cleanup: bool) -> None:
    dsn = os.environ.get("DB_DSN")
    if not dsn:
        print("DB_DSN not set; refusing to guess a connection string.", file=sys.stderr)
        sys.exit(2)

    print("=" * 70)
    print("  TAD backend <-> Postgres connectivity check")
    print("=" * 70)
    print(f"  DSN: {dsn}")

    engine = build_engine(dsn)
    factory = build_session_factory(engine)

    before = await _row_counts(factory)
    _print_counts("row counts (before):", before)

    await _roundtrip(factory, cleanup=cleanup)

    after = await _row_counts(factory)
    _print_counts("row counts (after):", after)
    await engine.dispose()
    print("  connection closed cleanly")


def main() -> None:
    ap = argparse.ArgumentParser(description="TAD backend <-> Postgres connectivity check.")
    ap.add_argument(
        "--cleanup",
        action="store_true",
        help="Delete the probe rows before exit (default: leave them for inspection).",
    )
    args = ap.parse_args()
    asyncio.run(_amain(cleanup=args.cleanup))


if __name__ == "__main__":
    main()
