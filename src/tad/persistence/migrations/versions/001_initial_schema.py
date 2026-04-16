"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-17 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("started_by", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("left_dir", sa.Text, nullable=False),
        sa.Column("right_dir", sa.Text, nullable=False),
        sa.Column("algo_params_version", sa.String(32), nullable=False),
        sa.Column("shift", sa.String(8)),
        sa.Column("area", sa.String(32)),
        sa.Column("notes", sa.Text),
        sa.Column("summary_json", postgresql.JSONB),
        sa.CheckConstraint("status IN ('ACTIVE','STOPPED','FAILED')", name="ck_sessions_status"),
    )
    op.create_index("ix_sessions_started_at", "sessions", ["started_at"])

    op.create_table(
        "measurements",
        sa.Column("measurement_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.session_id"),
            nullable=False,
        ),
        sa.Column("chassis_no", sa.String(17), nullable=False),
        sa.Column("camera_side", sa.CHAR(1), nullable=False),
        sa.Column("image_path", sa.Text, nullable=False),
        sa.Column("diameter_mm", sa.Numeric(6, 3)),
        sa.Column("tolerance_min_mm", sa.Numeric(6, 3), nullable=False),
        sa.Column("tolerance_max_mm", sa.Numeric(6, 3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("confidence_score", sa.Numeric(4, 3)),
        sa.Column("circle_center_x_px", sa.Integer),
        sa.Column("circle_center_y_px", sa.Integer),
        sa.Column("radius_px", sa.Numeric(8, 3)),
        sa.Column("mm_per_px", sa.Numeric(8, 6), nullable=False),
        sa.Column("calibration_version", sa.String(32), nullable=False),
        sa.Column("algo_params_version", sa.String(32), nullable=False),
        sa.Column("debug_image_key", sa.Text),
        sa.Column("error_code", sa.String(32)),
        sa.Column("error_message", sa.Text),
        sa.Column("processed_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=False),
        sa.CheckConstraint("camera_side IN ('L','R')", name="ck_meas_camera_side"),
        sa.CheckConstraint("status IN ('PASS','FAIL','REVIEW','ERROR')", name="ck_meas_status"),
    )
    op.create_index("ix_measurements_session_chassis", "measurements", ["session_id", "chassis_no"])
    op.create_index("ix_measurements_chassis_no", "measurements", ["chassis_no"])
    op.create_index("ix_measurements_processed_at", "measurements", ["processed_at"])

    op.create_table(
        "chassis_records",
        sa.Column("chassis_record_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "session_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sessions.session_id"),
            nullable=False,
        ),
        sa.Column("chassis_no", sa.String(17), nullable=False),
        sa.Column(
            "left_measurement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("measurements.measurement_id"),
        ),
        sa.Column(
            "right_measurement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("measurements.measurement_id"),
        ),
        sa.Column("left_diameter_mm", sa.Numeric(6, 3)),
        sa.Column("right_diameter_mm", sa.Numeric(6, 3)),
        sa.Column("avg_diameter_mm", sa.Numeric(6, 3)),
        sa.Column("asymmetry_mm", sa.Numeric(6, 3)),
        sa.Column("overall_status", sa.String(16), nullable=False),
        sa.Column("reason", sa.Text),
        sa.Column("operator_decision", sa.String(16)),
        sa.Column("decided_by", sa.String(64)),
        sa.Column("decided_at", sa.TIMESTAMP(timezone=True)),
        sa.Column("flagged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("shift", sa.String(8)),
        sa.Column("area", sa.String(32)),
        sa.Column("aggregated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.UniqueConstraint("session_id", "chassis_no", name="uq_session_chassis"),
    )
    op.create_index("ix_chassis_records_chassis_no", "chassis_records", ["chassis_no"])
    op.create_index("ix_chassis_records_agg_at", "chassis_records", ["aggregated_at"])

    op.create_table(
        "calibrations",
        sa.Column("calibration_id", sa.String(32), primary_key=True),
        sa.Column("camera_side", sa.CHAR(1), nullable=False),
        sa.Column("mm_per_px", sa.Numeric(8, 6), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("valid_from", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("operator", sa.String(64), nullable=False),
        sa.Column("reference_image", sa.Text),
        sa.Column(
            "imported_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint("camera_side IN ('L','R')", name="ck_cal_camera_side"),
    )


def downgrade() -> None:
    op.drop_table("calibrations")
    op.drop_index("ix_chassis_records_agg_at", table_name="chassis_records")
    op.drop_index("ix_chassis_records_chassis_no", table_name="chassis_records")
    op.drop_table("chassis_records")
    op.drop_index("ix_measurements_processed_at", table_name="measurements")
    op.drop_index("ix_measurements_chassis_no", table_name="measurements")
    op.drop_index("ix_measurements_session_chassis", table_name="measurements")
    op.drop_table("measurements")
    op.drop_index("ix_sessions_started_at", table_name="sessions")
    op.drop_table("sessions")
