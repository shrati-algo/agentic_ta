"""End-to-end session flow.

Exercises the whole backend via HTTP:
  1. POST /v1/sessions/start
  2. Feed two fixture images directly through ``process_item`` (simulating
     what the real folder-watcher would do in production, but without the
     threadpool/event-loop plumbing that doesn't survive a ``TestClient``
     per-request loop).
  3. GET /v1/chassis, GET /v1/chassis/{id}, GET /v1/debug/{id}
  4. POST /v1/chassis/{id}/decision, /flag
  5. GET /v1/dashboard/summary
  6. POST /v1/sessions/{id}/stop -> verifies summary counts
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from uuid import UUID

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from tad.api.app import create_app
from tad.config.algo_params import load_algo_params
from tad.config.calibration import load_calibration
from tad.config.settings import Settings
from tad.persistence.blob_store import InMemoryBlobStore
from tad.sessions.consumer import process_item
from tad.sessions.watcher import QueueItem
from tests.fakes import (
    InMemoryChassisRepository,
    InMemoryMeasurementRepository,
    InMemorySessionRepository,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIGS = REPO_ROOT / "configs"


def _make_synthetic_circle_jpg(radius: int = 160) -> bytes:
    """Bright plate (1600x2200) with a dark hole, meeting the validator's
    min_resolution=2048x1536 gate (width x height in the validator is
    image.shape[1] x image.shape[0], i.e. 2200 x 1600)."""
    img = np.full((1600, 2200, 3), 220, dtype=np.uint8)
    cv2.circle(img, (1100, 800), radius, (30, 30, 30), -1)
    # Add a little texture so the Laplacian variance passes
    rng = np.random.default_rng(seed=42)
    noise = rng.integers(-10, 10, size=img.shape, dtype=np.int16)
    img = np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    return buf.tobytes()


@pytest.fixture
def e2e_app(tmp_path: Path):  # type: ignore[no-untyped-def]
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()

    algo = load_algo_params("algo-1.3.0", base_dir=CONFIGS / "algo_params")
    # Synthetic circle radius 160 px * 2 * 0.08234 mm/px = 26.35 mm
    algo = algo.model_copy(
        update={
            "target": algo.target.model_copy(
                update={"diameter_mm": 26.35, "radius_tolerance_mm": 3.0}
            ),
            "tolerance": algo.tolerance.model_copy(
                update={
                    "min_mm": 20.0,
                    "max_mm": 32.0,
                    "ok_band_mm": 1.0,
                    "somewhat_ok_band_mm": 3.0,
                }
            ),
            "hough": algo.hough.model_copy(update={"param2": 15}),
        }
    )

    settings = Settings(
        db_dsn="postgresql+psycopg://unused/unused",
        minio_endpoint="unused",
        minio_access_key="unused",
        minio_secret_key="unused",
        minio_bucket="tad-debug",
        images_left_dir=str(left),
        images_right_dir=str(right),
        algo_params_version="algo-1.3.0",
        default_calibration_left=str(CONFIGS / "calibration" / "cal-2026-03-14-L.yaml"),
        default_calibration_right=str(CONFIGS / "calibration" / "cal-2026-03-14-R.yaml"),
        log_level="WARNING",
        demo_enabled=True,
    )

    app = create_app(
        settings=settings,
        algo_params=algo,
        left_calibration=load_calibration(settings.default_calibration_left),
        right_calibration=load_calibration(settings.default_calibration_right),
        session_repo=InMemorySessionRepository(),
        meas_repo=InMemoryMeasurementRepository(),
        chassis_repo=InMemoryChassisRepository(),
        blob_store=InMemoryBlobStore(),
        start_watchers=False,
        run_consumer=False,
    )
    with TestClient(app) as client:
        yield client, app, left, right


class TestFullSessionFlow:
    def test_start_drop_receive_events_stop(self, e2e_app) -> None:  # type: ignore[no-untyped-def]
        client, app, left_dir, right_dir = e2e_app

        r = client.post(
            "/v1/sessions/start",
            json={"started_by": "op-1", "shift": "A", "area": "Welding"},
        )
        assert r.status_code == 201, r.text
        start_body = r.json()
        session_id: UUID = UUID(start_body["session_id"])
        assert start_body["algo_params_version"] == "algo-1.3.0"

        jpg = _make_synthetic_circle_jpg()
        left_path = left_dir / "ABC12345678901234_L.jpg"
        right_path = right_dir / "ABC12345678901234_R.jpg"
        left_path.write_bytes(jpg)
        right_path.write_bytes(jpg)

        rt = app.state.session_manager.require_active(session_id)

        async def _drive() -> None:
            await process_item(QueueItem(side="L", path=left_path), rt)
            await process_item(QueueItem(side="R", path=right_path), rt)

        asyncio.run(_drive())

        assert len(app.state.meas_repo.rows) == 2
        assert len(app.state.chassis_repo.rows) == 1

        r = client.get("/v1/chassis")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        crid = body["items"][0]["chassis_record_id"]
        assert body["items"][0]["shift"] == "A"

        r = client.get(f"/v1/chassis/{crid}")
        assert r.status_code == 200
        detail = r.json()
        assert detail["chassis_no"] == "ABC12345678901234"
        assert detail["left"] is not None
        assert detail["right"] is not None
        assert detail["left"]["debug_image_url"].startswith("/v1/debug/")

        left_mid = detail["left"]["measurement_id"]
        r = client.get(f"/v1/debug/{left_mid}")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/jpeg")
        assert len(r.content) > 0

        r = client.post(
            f"/v1/chassis/{crid}/decision",
            json={"decision": "CORRECT", "decided_by": "op-42"},
        )
        assert r.status_code == 200
        assert r.json()["operator_decision"] == "CORRECT"

        r = client.post(
            f"/v1/chassis/{crid}/flag",
            json={"flagged": True, "by": "op-42"},
        )
        assert r.status_code == 200
        assert r.json()["flagged"] is True

        r = client.get("/v1/dashboard/summary")
        assert r.status_code == 200
        summary = r.json()
        assert summary["total"] == 1
        status_total = summary["pass"] + summary["review"] + summary["fail"]
        assert status_total == 1

        r = client.post(f"/v1/sessions/{session_id}/stop")
        assert r.status_code == 200, r.text
        stop_body = r.json()
        assert stop_body["status"] == "STOPPED"
        assert stop_body["summary"]["total"] == 1

    def test_bad_filename_emits_warning(self, e2e_app) -> None:  # type: ignore[no-untyped-def]
        client, app, left_dir, _right_dir = e2e_app

        r = client.post("/v1/sessions/start", json={"started_by": "op-1"})
        assert r.status_code == 201
        session_id = UUID(r.json()["session_id"])

        rt = app.state.session_manager.require_active(session_id)

        bad = left_dir / "this_is_not_a_valid_name.jpg"
        bad.write_bytes(_make_synthetic_circle_jpg())

        async def _drive() -> str:
            q = rt.broker.subscribe()
            await process_item(QueueItem(side="L", path=bad), rt)
            evt = await asyncio.wait_for(q.get(), timeout=5.0)
            while evt.type == "session_opened":
                evt = await asyncio.wait_for(q.get(), timeout=5.0)
            rt.broker.unsubscribe(q)
            return evt.type

        event_type = asyncio.run(_drive())
        assert event_type == "warning"

        client.post(f"/v1/sessions/{session_id}/stop")
