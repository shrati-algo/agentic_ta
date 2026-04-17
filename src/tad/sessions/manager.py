"""Session lifecycle manager.

Owns the table of active sessions (one process -> one SessionManager ->
zero or one active sessions for v1).  Responsible for validating
preconditions, spinning up the runtime, and driving the stop flow.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from tad.api.errors import (
    FolderUnavailableError,
    NoCalibrationError,
    SessionAlreadyActiveError,
    SessionNotActiveError,
)
from tad.config.algo_params import AlgoParams
from tad.config.calibration import Calibration
from tad.persistence.blob_store import DebugImageStore
from tad.persistence.models import SessionRow
from tad.persistence.repositories import (
    ChassisRepository,
    MeasurementRepository,
    SessionRepository,
)
from tad.sessions.aggregator import Aggregator
from tad.sessions.broker import Event, SseBroker
from tad.sessions.consumer import consumer_loop
from tad.sessions.runtime import SessionRuntime
from tad.sessions.watcher import FolderWatcher, QueueItem


class SessionManager:
    def __init__(
        self,
        *,
        algo_params: AlgoParams,
        left_calibration: Calibration,
        right_calibration: Calibration,
        left_dir: Path,
        right_dir: Path,
        session_repo: SessionRepository,
        meas_repo: MeasurementRepository,
        chassis_repo: ChassisRepository,
        blob_store: DebugImageStore,
        queue_max_size: int = 256,
        broker_queue_max_size: int = 128,
        debug_image_base_url: str = "/v1/debug",
        start_watchers: bool = True,
        run_consumer: bool = True,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._algo_params = algo_params
        self._left_calibration = left_calibration
        self._right_calibration = right_calibration
        self._left_dir = left_dir
        self._right_dir = right_dir
        self._session_repo = session_repo
        self._meas_repo = meas_repo
        self._chassis_repo = chassis_repo
        self._blob_store = blob_store
        self._queue_max_size = queue_max_size
        self._broker_queue_max_size = broker_queue_max_size
        self._debug_image_base_url = debug_image_base_url
        self._start_watchers = start_watchers
        self._run_consumer = run_consumer
        self._clock = clock

        self._active: dict[UUID, SessionRuntime] = {}
        self._stop_events: dict[UUID, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    # -- public API -----------------------------------------------------

    @property
    def algo_params(self) -> AlgoParams:
        return self._algo_params

    def require_active(self, session_id: UUID) -> SessionRuntime:
        rt = self._active.get(session_id)
        if rt is None:
            msg = f"session {session_id} is not active"
            raise SessionNotActiveError(msg)
        return rt

    def active_sessions(self) -> list[SessionRuntime]:
        return list(self._active.values())

    async def start(
        self,
        *,
        started_by: str,
        shift: str | None = None,
        area: str | None = None,
        notes: str | None = None,
    ) -> SessionRuntime:
        async with self._lock:
            if self._active:
                msg = "a session is already active"
                raise SessionAlreadyActiveError(msg)

            # Preconditions: folders and calibrations
            if not self._left_dir.is_dir():
                msg = f"left image dir unreachable: {self._left_dir}"
                raise FolderUnavailableError(msg)
            if not self._right_dir.is_dir():
                msg = f"right image dir unreachable: {self._right_dir}"
                raise FolderUnavailableError(msg)
            if self._left_calibration is None:
                raise NoCalibrationError("left calibration missing")
            if self._right_calibration is None:
                raise NoCalibrationError("right calibration missing")

            session_id = uuid4()
            now = self._clock()
            session_row = SessionRow(
                session_id=session_id,
                started_at=now,
                stopped_at=None,
                started_by=started_by,
                status="ACTIVE",
                left_dir=str(self._left_dir),
                right_dir=str(self._right_dir),
                algo_params_version=self._algo_params.version,
                shift=shift,
                area=area,
                notes=notes,
            )
            await self._session_repo.create(session_row)

            queue: asyncio.Queue[QueueItem] = asyncio.Queue(maxsize=self._queue_max_size)
            broker = SseBroker(queue_max_size=self._broker_queue_max_size)

            async def _emit(row):  # type: ignore[no-untyped-def]
                await broker.publish(
                    Event(
                        type="chassis_result",
                        payload={
                            "chassis_record_id": str(row.chassis_record_id),
                            "chassis_no": row.chassis_no,
                            "left_diameter_mm": row.left_diameter_mm,
                            "right_diameter_mm": row.right_diameter_mm,
                            "avg_diameter_mm": row.avg_diameter_mm,
                            "asymmetry_mm": row.asymmetry_mm,
                            "overall_status": row.overall_status,
                            "shift": row.shift,
                            "area": row.area,
                            "aggregated_at": row.aggregated_at.isoformat(),
                        },
                    )
                )

            aggregator = Aggregator(
                session_id=session_id,
                chassis_repo=self._chassis_repo,
                emit=_emit,
                asymmetry_threshold_mm=self._algo_params.tolerance.asymmetry_threshold_mm,
                shift=shift,
                area=area,
                clock=self._clock,
            )

            calibrations = {
                "L": self._left_calibration,
                "R": self._right_calibration,
            }

            rt = SessionRuntime(
                session=session_row,
                algo_params=self._algo_params,
                calibrations=calibrations,
                queue=queue,
                broker=broker,
                aggregator=aggregator,
                meas_repo=self._meas_repo,
                chassis_repo=self._chassis_repo,
                session_repo=self._session_repo,
                blob_store=self._blob_store,
                debug_image_base_url=self._debug_image_base_url,
            )

            if self._start_watchers:
                loop = asyncio.get_running_loop()
                sides: list[tuple[Literal["L", "R"], Path]] = [
                    ("L", self._left_dir),
                    ("R", self._right_dir),
                ]
                for side, path in sides:
                    watcher = FolderWatcher(side, path, queue, loop=loop)
                    watcher.start()
                    rt.watchers.append(watcher)

            if self._run_consumer:
                stop_event = asyncio.Event()
                self._stop_events[session_id] = stop_event
                rt.consumer_task = asyncio.create_task(consumer_loop(rt, stop_event=stop_event))

            self._active[session_id] = rt

            # Emit session_opened
            await broker.publish(
                Event(
                    type="session_opened",
                    payload={
                        "session_id": str(session_id),
                        "started_at": now.isoformat(),
                        "algo_params_version": self._algo_params.version,
                        "left_calibration": self._left_calibration.calibration_id,
                        "right_calibration": self._right_calibration.calibration_id,
                    },
                )
            )

            return rt

    async def stop(self, session_id: UUID, *, drain_timeout: float = 10.0) -> dict[str, Any]:
        async with self._lock:
            rt = self._active.get(session_id)
            if rt is None:
                msg = f"session {session_id} is not active"
                raise SessionNotActiveError(msg)

            # Stop producers first (no new items)
            for w in rt.watchers:
                w.stop()
            rt.watchers.clear()

            # Wait for queue to drain, then signal consumer to exit
            deadline = asyncio.get_event_loop().time() + drain_timeout
            while not rt.queue.empty() and asyncio.get_event_loop().time() < deadline:
                await asyncio.sleep(0.05)

            stop_event = self._stop_events.pop(session_id, None)
            if stop_event is not None:
                stop_event.set()
            if rt.consumer_task is not None:
                try:
                    await asyncio.wait_for(rt.consumer_task, timeout=drain_timeout)
                except TimeoutError:
                    rt.consumer_task.cancel()

            # Flush orphans
            await rt.aggregator.flush()

            # Compute summary
            measurements = await rt.meas_repo.list_by_session(session_id)
            chassis_rows, _ = await rt.chassis_repo.list_page(page=1, page_size=10_000)
            chassis_rows = [r for r in chassis_rows if r.session_id == session_id]

            def _count(rows: list, statuses: set[str]) -> int:  # type: ignore[type-arg]
                return sum(1 for r in rows if r.overall_status in statuses)

            summary: dict[str, Any] = {
                "total": len(chassis_rows),
                "pass": _count(chassis_rows, {"PASS"}),
                "review": _count(chassis_rows, {"REVIEW"}),
                "fail": _count(chassis_rows, {"FAIL"}),
                "error": _count(chassis_rows, {"ERROR"}),
                "incomplete": sum(1 for r in chassis_rows if r.reason),
                "measurements_total": len(measurements),
            }

            stopped_at = self._clock()
            await self._session_repo.mark_stopped(session_id, stopped_at, summary)

            # Emit session_closed, then close the broker
            await rt.broker.publish(
                Event(
                    type="session_closed",
                    payload={
                        "session_id": str(session_id),
                        "stopped_at": stopped_at.isoformat(),
                        "summary": summary,
                    },
                )
            )
            await rt.broker.close()

            self._active.pop(session_id, None)
            return {"session_id": session_id, "stopped_at": stopped_at, "summary": summary}
