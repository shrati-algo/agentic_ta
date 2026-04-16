"""HTTP-level integration tests for the main API routes.

These run against the FastAPI app wired with in-memory repositories +
blob store, so they need neither Postgres nor MinIO.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from tad.persistence.models import ChassisRow, MeasurementRow, SessionRow


class TestHealth:
    def test_health_returns_200(self, app_with_fakes: TestClient) -> None:
        r = app_with_fakes.get("/v1/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_ready_returns_200_when_prereqs_ok(self, app_with_fakes: TestClient) -> None:
        r = app_with_fakes.get("/v1/ready")
        assert r.status_code == 200
        assert r.json()["status"] == "ready"


class TestSessionLifecycle:
    def test_start_and_stop_session(self, app_with_fakes: TestClient) -> None:
        r = app_with_fakes.post(
            "/v1/sessions/start",
            json={"started_by": "op-1", "shift": "A", "area": "Welding"},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        session_id = body["session_id"]
        assert body["status"] == "ACTIVE"
        assert body["algo_params_version"] == "algo-1.3.0"
        assert body["left_calibration"] == "cal-2026-03-14-L"
        assert body["right_calibration"] == "cal-2026-03-14-R"

        r = app_with_fakes.post(f"/v1/sessions/{session_id}/stop")
        assert r.status_code == 200, r.text
        stop_body = r.json()
        assert stop_body["status"] == "STOPPED"
        assert stop_body["summary"]["total"] == 0

    def test_double_start_conflict(self, app_with_fakes: TestClient) -> None:
        r1 = app_with_fakes.post("/v1/sessions/start", json={"started_by": "op-1"})
        assert r1.status_code == 201
        r2 = app_with_fakes.post("/v1/sessions/start", json={"started_by": "op-1"})
        assert r2.status_code == 409
        assert r2.json()["error_code"] == "ERR_SESSION_ALREADY_ACTIVE"

    def test_stop_missing_session_404(self, app_with_fakes: TestClient) -> None:
        r = app_with_fakes.post(f"/v1/sessions/{uuid4()}/stop")
        assert r.status_code == 404
        assert r.json()["error_code"] == "ERR_SESSION_NOT_ACTIVE"

    def test_list_active_sessions(self, app_with_fakes: TestClient) -> None:
        r = app_with_fakes.post("/v1/sessions/start", json={"started_by": "op-1"})
        assert r.status_code == 201
        r = app_with_fakes.get("/v1/sessions?status=ACTIVE")
        assert r.status_code == 200
        assert len(r.json()) == 1


class TestChassisRoutes:
    def _seed(self, client: TestClient) -> tuple[UUID, UUID]:
        """Insert a session + chassis + two measurement rows directly into
        the in-memory repos so list/detail/decision/flag can be exercised."""
        state = client.app_state  # type: ignore[attr-defined]
        sid = uuid4()
        session = SessionRow(
            session_id=sid,
            started_at=datetime.now(UTC) - timedelta(hours=1),
            stopped_at=None,
            started_by="op-1",
            status="ACTIVE",
            left_dir="/tmp/l",
            right_dir="/tmp/r",
            algo_params_version="algo-1.3.0",
        )
        state.session_repo.rows[sid] = session

        left_id = uuid4()
        right_id = uuid4()
        now = datetime.now(UTC)
        state.meas_repo.rows[left_id] = MeasurementRow(
            measurement_id=left_id,
            session_id=sid,
            chassis_no="ABC12345678901234",
            camera_side="L",
            image_path="/tmp/l/file_L.jpg",
            diameter_mm=47.25,
            tolerance_min_mm=47.0,
            tolerance_max_mm=47.5,
            status="PASS",
            confidence_score=0.95,
            circle_center_x_px=100,
            circle_center_y_px=100,
            radius_px=286.9,
            mm_per_px=0.08234,
            calibration_version="cal-L",
            algo_params_version="algo-1.3.0",
            debug_image_key=f"sessions/{sid}/measurements/{left_id}.jpg",
            error_code=None,
            error_message=None,
            processed_at=now,
            latency_ms=120,
        )
        state.meas_repo.rows[right_id] = MeasurementRow(
            **{
                **state.meas_repo.rows[left_id].__dict__,
                "measurement_id": right_id,
                "camera_side": "R",
                "debug_image_key": f"sessions/{sid}/measurements/{right_id}.jpg",
            }
        )

        crid = uuid4()
        state.chassis_repo.rows[crid] = ChassisRow(
            chassis_record_id=crid,
            session_id=sid,
            chassis_no="ABC12345678901234",
            left_measurement_id=left_id,
            right_measurement_id=right_id,
            left_diameter_mm=47.25,
            right_diameter_mm=47.28,
            avg_diameter_mm=47.265,
            asymmetry_mm=0.03,
            overall_status="PASS",
            reason=None,
            aggregated_at=now,
            shift="A",
            area="Welding",
        )

        # Seed debug-image blobs so /v1/debug/{id} returns content
        import asyncio as _aio

        _aio.run(state.blob_store.put(state.meas_repo.rows[left_id].debug_image_key, b"JPEG-L"))
        _aio.run(state.blob_store.put(state.meas_repo.rows[right_id].debug_image_key, b"JPEG-R"))

        return crid, left_id

    def test_list_chassis(self, app_with_fakes: TestClient) -> None:
        crid, _ = self._seed(app_with_fakes)
        r = app_with_fakes.get("/v1/chassis?page=1&page_size=10")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["items"][0]["chassis_record_id"] == str(crid)
        assert body["items"][0]["overall_status"] == "PASS"

    def test_chassis_detail(self, app_with_fakes: TestClient) -> None:
        crid, _ = self._seed(app_with_fakes)
        r = app_with_fakes.get(f"/v1/chassis/{crid}")
        assert r.status_code == 200
        body = r.json()
        assert body["chassis_no"] == "ABC12345678901234"
        assert body["left"]["status"] == "PASS"
        assert body["right"]["status"] == "PASS"
        assert body["left"]["debug_image_url"].startswith("/v1/debug/")

    def test_chassis_not_found(self, app_with_fakes: TestClient) -> None:
        r = app_with_fakes.get(f"/v1/chassis/{uuid4()}")
        assert r.status_code == 404
        assert r.json()["error_code"] == "ERR_CHASSIS_NOT_FOUND"

    def test_record_decision(self, app_with_fakes: TestClient) -> None:
        crid, _ = self._seed(app_with_fakes)
        r = app_with_fakes.post(
            f"/v1/chassis/{crid}/decision",
            json={"decision": "CORRECT", "decided_by": "op-42"},
        )
        assert r.status_code == 200
        assert r.json()["operator_decision"] == "CORRECT"

    def test_flag(self, app_with_fakes: TestClient) -> None:
        crid, _ = self._seed(app_with_fakes)
        r = app_with_fakes.post(f"/v1/chassis/{crid}/flag", json={"flagged": True, "by": "op-42"})
        assert r.status_code == 200
        assert r.json()["flagged"] is True


class TestMeasurementRoutes:
    def test_get_measurement(self, app_with_fakes: TestClient) -> None:
        crid, mid = TestChassisRoutes()._seed(app_with_fakes)
        r = app_with_fakes.get(f"/v1/measurements/{mid}")
        assert r.status_code == 200
        assert r.json()["status"] == "PASS"

    def test_debug_image_streams(self, app_with_fakes: TestClient) -> None:
        crid, mid = TestChassisRoutes()._seed(app_with_fakes)
        r = app_with_fakes.get(f"/v1/debug/{mid}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/jpeg")
        assert r.content == b"JPEG-L"


class TestDashboardSummary:
    def test_summary_aggregates(self, app_with_fakes: TestClient) -> None:
        TestChassisRoutes()._seed(app_with_fakes)
        r = app_with_fakes.get("/v1/dashboard/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["pass"] == 1
        assert body["review"] == 0
        assert body["fail"] == 0
