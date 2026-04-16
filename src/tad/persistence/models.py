"""SQLAlchemy mapped classes and plain-dataclass DTOs.

The SQLAlchemy ORM classes (``Session``, ``Measurement``, ``ChassisRecord``,
``Calibration``) mirror the DDL in ``docs/architecture.txt`` Section 7.
Repositories translate between these mapped objects and the
``@dataclass(frozen=True)`` DTOs that the rest of the service uses — the
session runtime and the API layer never see a SQLAlchemy instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import (
    CHAR,
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all TAD ORM classes."""


# ---------------------------------------------------------------------------
# ORM classes (persistence)
# ---------------------------------------------------------------------------


class SessionORM(Base):
    __tablename__ = "sessions"

    session_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    stopped_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    started_by: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    left_dir: Mapped[str] = mapped_column(Text, nullable=False)
    right_dir: Mapped[str] = mapped_column(Text, nullable=False)
    algo_params_version: Mapped[str] = mapped_column(String(32), nullable=False)
    shift: Mapped[str | None] = mapped_column(String(8))
    area: Mapped[str | None] = mapped_column(String(32))
    notes: Mapped[str | None] = mapped_column(Text)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE','STOPPED','FAILED')", name="ck_sessions_status"),
        Index("ix_sessions_started_at", "started_at"),
    )


class MeasurementORM(Base):
    __tablename__ = "measurements"

    measurement_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("sessions.session_id"), nullable=False
    )
    chassis_no: Mapped[str] = mapped_column(String(17), nullable=False)
    camera_side: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    image_path: Mapped[str] = mapped_column(Text, nullable=False)
    diameter_mm: Mapped[float | None] = mapped_column(Numeric(6, 3))
    tolerance_min_mm: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    tolerance_max_mm: Mapped[float] = mapped_column(Numeric(6, 3), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    circle_center_x_px: Mapped[int | None] = mapped_column(Integer)
    circle_center_y_px: Mapped[int | None] = mapped_column(Integer)
    radius_px: Mapped[float | None] = mapped_column(Numeric(8, 3))
    mm_per_px: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    calibration_version: Mapped[str] = mapped_column(String(32), nullable=False)
    algo_params_version: Mapped[str] = mapped_column(String(32), nullable=False)
    debug_image_key: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(32))
    error_message: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        CheckConstraint("camera_side IN ('L','R')", name="ck_meas_camera_side"),
        CheckConstraint("status IN ('PASS','FAIL','REVIEW','ERROR')", name="ck_meas_status"),
        Index("ix_measurements_session_chassis", "session_id", "chassis_no"),
        Index("ix_measurements_chassis_no", "chassis_no"),
        Index("ix_measurements_processed_at", "processed_at"),
    )


class ChassisRecordORM(Base):
    __tablename__ = "chassis_records"

    chassis_record_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("sessions.session_id"), nullable=False
    )
    chassis_no: Mapped[str] = mapped_column(String(17), nullable=False)
    left_measurement_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("measurements.measurement_id")
    )
    right_measurement_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("measurements.measurement_id")
    )
    left_diameter_mm: Mapped[float | None] = mapped_column(Numeric(6, 3))
    right_diameter_mm: Mapped[float | None] = mapped_column(Numeric(6, 3))
    avg_diameter_mm: Mapped[float | None] = mapped_column(Numeric(6, 3))
    asymmetry_mm: Mapped[float | None] = mapped_column(Numeric(6, 3))
    overall_status: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    operator_decision: Mapped[str | None] = mapped_column(String(16))
    decided_by: Mapped[str | None] = mapped_column(String(64))
    decided_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True))
    flagged: Mapped[bool] = mapped_column(nullable=False, default=False)
    shift: Mapped[str | None] = mapped_column(String(8))
    area: Mapped[str | None] = mapped_column(String(32))
    aggregated_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("session_id", "chassis_no", name="uq_session_chassis"),
        Index("ix_chassis_records_chassis_no", "chassis_no"),
        Index("ix_chassis_records_agg_at", "aggregated_at"),
    )


class CalibrationORM(Base):
    __tablename__ = "calibrations"

    calibration_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    camera_side: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    mm_per_px: Mapped[float] = mapped_column(Numeric(8, 6), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    valid_from: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)
    operator: Mapped[str] = mapped_column(String(64), nullable=False)
    reference_image: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False)

    __table_args__ = (CheckConstraint("camera_side IN ('L','R')", name="ck_cal_camera_side"),)


# ---------------------------------------------------------------------------
# DTOs used by the rest of the service
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionRow:
    session_id: UUID
    started_at: datetime
    stopped_at: datetime | None
    started_by: str
    status: Literal["ACTIVE", "STOPPED", "FAILED"]
    left_dir: str
    right_dir: str
    algo_params_version: str
    shift: str | None = None
    area: str | None = None
    notes: str | None = None
    summary_json: dict[str, Any] | None = None


@dataclass(frozen=True)
class MeasurementRow:
    measurement_id: UUID
    session_id: UUID
    chassis_no: str
    camera_side: Literal["L", "R"]
    image_path: str
    diameter_mm: float | None
    tolerance_min_mm: float
    tolerance_max_mm: float
    status: Literal["PASS", "FAIL", "REVIEW", "ERROR"]
    confidence_score: float | None
    circle_center_x_px: int | None
    circle_center_y_px: int | None
    radius_px: float | None
    mm_per_px: float
    calibration_version: str
    algo_params_version: str
    debug_image_key: str | None
    error_code: str | None
    error_message: str | None
    processed_at: datetime
    latency_ms: int


@dataclass(frozen=True)
class ChassisRow:
    chassis_record_id: UUID
    session_id: UUID
    chassis_no: str
    left_measurement_id: UUID | None
    right_measurement_id: UUID | None
    left_diameter_mm: float | None
    right_diameter_mm: float | None
    avg_diameter_mm: float | None
    asymmetry_mm: float | None
    overall_status: Literal["PASS", "FAIL", "REVIEW", "ERROR"]
    reason: str | None
    aggregated_at: datetime
    operator_decision: Literal["CORRECT", "INCORRECT"] | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    flagged: bool = False
    shift: str | None = None
    area: str | None = None
    # Store whether user has updated fields (for upserts without surprise)
    _marker: int = field(default=0, repr=False)
