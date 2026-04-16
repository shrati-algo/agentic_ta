"""Pydantic request/response models for every API boundary.

All HTTP traffic goes through these models -- no raw dicts on the wire.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

Status = Literal["PASS", "FAIL", "REVIEW", "ERROR"]
CameraSide = Literal["L", "R"]
SessionStatus = Literal["ACTIVE", "STOPPED", "FAILED"]
OperatorDecision = Literal["CORRECT", "INCORRECT"]


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ErrorEnvelope(BaseModel):
    """Response body for every non-2xx response."""

    error_code: str
    error_message: str
    request_id: str


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


class StartRequest(BaseModel):
    started_by: str
    shift: Literal["A", "B", "C"] | None = None
    area: str | None = None
    notes: str | None = None


class StartResponse(BaseModel):
    session_id: UUID
    status: Literal["ACTIVE"]
    left_dir: str
    right_dir: str
    algo_params_version: str
    left_calibration: str
    right_calibration: str
    started_at: datetime


class SessionSummary(BaseModel):
    total: int
    pass_: int = Field(..., alias="pass")
    review: int
    fail: int
    error: int
    incomplete: int

    model_config = {"populate_by_name": True}


class StopResponse(BaseModel):
    session_id: UUID
    status: Literal["STOPPED"]
    stopped_at: datetime
    summary: SessionSummary


class SessionInfo(BaseModel):
    """Used by GET /v1/sessions?status=ACTIVE to discover an active session."""

    session_id: UUID
    status: SessionStatus
    started_at: datetime
    stopped_at: datetime | None = None
    algo_params_version: str


# ---------------------------------------------------------------------------
# Measurements / per-camera results
# ---------------------------------------------------------------------------


class MeasurementResponse(BaseModel):
    measurement_id: UUID
    session_id: UUID
    chassis_no: str
    camera_side: CameraSide
    diameter_mm: float | None
    status: Status
    confidence_score: float | None
    mm_per_px: float
    calibration_version: str
    algo_params_version: str
    debug_image_url: str | None
    error_code: str | None
    error_message: str | None
    processed_at: datetime
    latency_ms: int


# ---------------------------------------------------------------------------
# Chassis records
# ---------------------------------------------------------------------------


class ChassisListItem(BaseModel):
    """Row shape for the Dashboard table (TRD 8.4)."""

    chassis_record_id: UUID
    chassis_no: str
    overall_status: Status
    avg_diameter_mm: float | None
    timestamp: datetime
    shift: str | None = None
    area: str | None = None
    flagged: bool


class ChassisListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ChassisListItem]


class ChassisPerCamera(BaseModel):
    measurement_id: UUID
    diameter_mm: float | None
    status: Status
    confidence: float | None
    debug_image_url: str


class ChassisDetail(BaseModel):
    """Full chassis record for the Violation Detail page (TRD 8.5)."""

    chassis_record_id: UUID
    chassis_no: str
    overall_status: Status
    flagged: bool
    timestamp: datetime
    shift: str | None = None
    area: str | None = None
    left: ChassisPerCamera | None
    right: ChassisPerCamera | None
    operator_decision: OperatorDecision | None = None


class DecisionRequest(BaseModel):
    decision: OperatorDecision
    decided_by: str


class FlagRequest(BaseModel):
    flagged: bool
    by: str


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------


class TrendPoint(BaseModel):
    date: str  # YYYY-MM-DD
    review: int
    fail: int


class RecentAlert(BaseModel):
    chassis_record_id: UUID
    chassis_no: str
    timestamp: datetime
    overall_status: Status


class DashboardSummary(BaseModel):
    total: int
    pass_: int = Field(..., alias="pass")
    review: int
    fail: int
    violation_pct: float
    trend: list[TrendPoint]
    recent_alerts: list[RecentAlert]

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# SSE events (reference shapes; emitted as JSON in `data:`)
# ---------------------------------------------------------------------------


class SessionOpenedEvent(BaseModel):
    session_id: UUID
    started_at: datetime
    algo_params_version: str
    left_calibration: str
    right_calibration: str


class CameraResultEvent(BaseModel):
    measurement_id: UUID
    chassis_no: str
    camera_side: CameraSide
    diameter_mm: float | None
    status: Status
    confidence_score: float | None
    processed_at: datetime
    debug_image_url: str | None


class ChassisResultEvent(BaseModel):
    chassis_record_id: UUID
    chassis_no: str
    left_diameter_mm: float | None
    right_diameter_mm: float | None
    avg_diameter_mm: float | None
    asymmetry_mm: float | None
    overall_status: Status
    shift: str | None = None
    area: str | None = None
    aggregated_at: datetime


class WarningEvent(BaseModel):
    chassis_no: str | None
    file: str
    error_code: str
    message: str


class SessionClosedEvent(BaseModel):
    session_id: UUID
    stopped_at: datetime
    summary: SessionSummary


# ---------------------------------------------------------------------------
# Internal event envelope used on the broker (not on the wire verbatim)
# ---------------------------------------------------------------------------


class BrokerEvent(BaseModel):
    type: Literal[
        "session_opened",
        "camera_result",
        "chassis_result",
        "warning",
        "session_closed",
    ]
    payload: dict[str, Any]
