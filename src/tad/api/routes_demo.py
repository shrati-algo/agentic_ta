"""Demo-only endpoints.

These live under ``/v1/demo/*`` and are intended for local-host UI demos.
They are **not** part of the production API surface (TRD Section 8).

The replay route copies matched L/R image pairs from a source folder
into the session's watched folders at a configurable interval, so the
dashboard fills up automatically without anyone dropping files by hand.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from tad.api.deps import get_session_manager
from tad.api.errors import TadError
from tad.workers.manager import SessionManager
from tad.workers.runtime import SessionRuntime

router = APIRouter(prefix="/v1/demo", tags=["demo"])


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class _ReplayState:
    running: bool = False
    source_dir: str | None = None
    interval_s: float = 20.0
    pairs_sent: int = 0
    total_pairs: int = 0
    task: asyncio.Task[None] | None = field(default=None, repr=False)
    stop_event: asyncio.Event | None = field(default=None, repr=False)


# A single replay per process is enough for a demo.
_state = _ReplayState()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class ReplayStartRequest(BaseModel):
    source_dir: str | None = None
    interval_seconds: float = 20.0
    max_pairs: int | None = None


class ReplayStatus(BaseModel):
    running: bool
    source_dir: str | None
    interval_seconds: float
    pairs_sent: int
    total_pairs: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VIN_ALPHABET = "ABCDEFGHJKLMNPRSTUVWXYZ0123456789"  # no I, O, Q


def _gen_chassis_no(index: int) -> str:
    """Return a 17-char VIN-compliant chassis number derived from *index*.

    Uses a fixed ``DMAX`` prefix plus the zero-padded index so runs are
    reproducible and easy to spot in the UI.  No I / O / Q anywhere
    (VIN-format requirement — see tad.ingestion.filename_parser).
    """
    prefix = "DMAX"  # 4 chars, no I/O/Q
    idx = max(0, int(index))
    chars: list[str] = []
    for _ in range(13):
        chars.append(_VIN_ALPHABET[idx % len(_VIN_ALPHABET)])
        idx //= len(_VIN_ALPHABET)
    return prefix + "".join(reversed(chars))


def _pair_source_files(source: Path) -> list[tuple[Path, Path]]:
    """Sort L and R images in ``source`` and pair them by index."""
    left = sorted(p for p in source.glob("*_L.jpg"))
    right = sorted(p for p in source.glob("*_R.jpg"))
    return list(zip(left, right, strict=False))


def _default_source_dir() -> str:
    """Project-root-relative default for the demo fixtures folder."""
    root = Path(__file__).resolve().parents[3]
    return str(root / "tests" / "fixtures" / "test_images" / "yca_valid")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/replay/start", response_model=ReplayStatus)
async def start_replay(
    body: ReplayStartRequest,
    mgr: SessionManager = Depends(get_session_manager),
) -> ReplayStatus:
    """Begin (or report the running) replay task.

    Idempotent: calling it while a replay is already running returns the
    current status without starting a second task.
    """
    if _state.running and _state.task and not _state.task.done():
        return _as_status()

    source = Path(body.source_dir or _default_source_dir())
    if not source.is_dir():
        raise TadError(f"replay source_dir not found: {source}")

    pairs = _pair_source_files(source)
    if body.max_pairs is not None:
        pairs = pairs[: body.max_pairs]
    if not pairs:
        raise TadError(f"no matched L/R pairs in {source}")

    # Ensure a session is running so the watchers pick our files up.
    active = mgr.active_sessions()
    if active:
        rt = active[0]
    else:
        rt = await mgr.start(started_by="demo-replay", shift="A", area="Welding")

    stop_event = asyncio.Event()
    _state.running = True
    _state.source_dir = str(source)
    _state.interval_s = float(body.interval_seconds)
    _state.pairs_sent = 0
    _state.total_pairs = len(pairs)
    _state.stop_event = stop_event
    _state.task = asyncio.create_task(_replay_loop(rt, pairs, body.interval_seconds, stop_event))

    return _as_status()


@router.post("/replay/stop", response_model=ReplayStatus)
async def stop_replay() -> ReplayStatus:
    if _state.stop_event is not None:
        _state.stop_event.set()
    if _state.task is not None:
        try:
            await asyncio.wait_for(_state.task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            _state.task.cancel()
    _state.running = False
    return _as_status()


@router.get("/replay/status", response_model=ReplayStatus)
async def replay_status() -> ReplayStatus:
    return _as_status()


# ---------------------------------------------------------------------------
# Loop
# ---------------------------------------------------------------------------


async def _replay_loop(
    rt: SessionRuntime,
    pairs: list[tuple[Path, Path]],
    interval_s: float,
    stop_event: asyncio.Event,
) -> None:
    left_dir = Path(rt.session.left_dir)
    right_dir = Path(rt.session.right_dir)
    left_dir.mkdir(parents=True, exist_ok=True)
    right_dir.mkdir(parents=True, exist_ok=True)

    try:
        for idx, (src_l, src_r) in enumerate(pairs):
            if stop_event.is_set():
                break
            chassis = _gen_chassis_no(idx)

            left_path = left_dir / f"{chassis}_L.jpg"
            right_path = right_dir / f"{chassis}_R.jpg"
            left_path.write_bytes(src_l.read_bytes())
            right_path.write_bytes(src_r.read_bytes())

            # Drive the consumer directly -- bypasses watchdog (whose
            # Windows ReadDirectoryChangesW buffer can drop fast events).
            for side, path in (("L", left_path), ("R", right_path)):
                try:
                    await _drive_one(rt, side, path)
                except Exception as exc:
                    import traceback

                    print(f"[replay] {chassis} {side} failed: {exc!r}", flush=True)
                    traceback.print_exc()

            _state.pairs_sent = idx + 1

            if idx == len(pairs) - 1:
                break
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_s)
                break  # stop requested
            except TimeoutError:
                continue
    finally:
        _state.running = False


async def _drive_one(rt: SessionRuntime, side: str, path: Path) -> None:
    """Inline copy of the consumer pipeline for the replay task.

    This is kept separate from :func:`tad.workers.consumer.process_item`
    because the replay needs to (a) bypass the watchdog observer on
    Windows and (b) feed measurements straight into the in-memory repo
    without going through a queue.
    """
    import time as _time
    from datetime import UTC, datetime
    from uuid import uuid4

    import cv2 as _cv2

    from tad.api.errors import BadFilename
    from tad.ingestion.filename_parser import parse_filename
    from tad.ingestion.image_validator import validate_image
    from tad.persistence.models import MeasurementRow
    from tad.processing.models import PipelineInput
    from tad.processing.pipeline import measure_innermost_diameter
    from tad.workers.broker import Event

    del side  # parsed below
    try:
        parsed = parse_filename(path.name)
    except BadFilename:
        return

    data = path.read_bytes()
    image, vr = validate_image(data)
    if not vr.ok or image is None:
        return

    cal = rt.calibrations[parsed.camera_side]
    algo = rt.algo_params
    inp = PipelineInput(
        image_bgr=image,
        calibration_mm_per_px=cal.mm_per_px,
        algo_params_version=algo.version,
        blur_kernel=algo.blur.kernel,
        threshold_block_size=algo.threshold.block_size,
        threshold_c=algo.threshold.c,
        morph_kernel_size=algo.morphology.kernel_size,
        morph_iterations=algo.morphology.iterations,
        contour_min_area=algo.contour.min_area,
        hough_dp=algo.hough.dp,
        hough_min_dist=algo.hough.min_dist,
        hough_param1=algo.hough.param1,
        hough_param2=algo.hough.param2,
        target_diameter_mm=algo.target.diameter_mm,
        radius_tolerance_mm=algo.target.radius_tolerance_mm,
        ok_band_mm=algo.tolerance.ok_band_mm,
        somewhat_ok_band_mm=algo.tolerance.somewhat_ok_band_mm,
        tolerance_min_mm=algo.tolerance.min_mm,
        tolerance_max_mm=algo.tolerance.max_mm,
    )

    t0 = _time.perf_counter()
    output = await asyncio.to_thread(measure_innermost_diameter, inp)
    latency_ms = int((_time.perf_counter() - t0) * 1000)

    measurement_id = uuid4()
    debug_key = f"sessions/{rt.session.session_id}/measurements/{measurement_id}.jpg"
    ok_encode, encoded = _cv2.imencode(".jpg", output.annotated_image)
    if ok_encode:
        await rt.blob_store.put(debug_key, encoded.tobytes())
    circle = output.circle
    row = MeasurementRow(
        measurement_id=measurement_id,
        session_id=rt.session.session_id,
        chassis_no=parsed.chassis_no,
        camera_side=parsed.camera_side,
        image_path=str(path),
        diameter_mm=output.diameter_mm,
        tolerance_min_mm=algo.tolerance.min_mm,
        tolerance_max_mm=algo.tolerance.max_mm,
        status=output.status,
        confidence_score=output.confidence,
        circle_center_x_px=int(circle[0]) if circle else None,
        circle_center_y_px=int(circle[1]) if circle else None,
        radius_px=float(circle[2]) if circle else None,
        mm_per_px=cal.mm_per_px,
        calibration_version=cal.calibration_id,
        algo_params_version=algo.version,
        debug_image_key=debug_key if ok_encode else None,
        error_code=output.error_code,
        error_message=None,
        processed_at=datetime.now(UTC),
        latency_ms=latency_ms,
    )
    await rt.meas_repo.insert(row)
    await rt.broker.publish(
        Event(
            type="camera_result",
            payload={
                "measurement_id": str(row.measurement_id),
                "chassis_no": row.chassis_no,
                "camera_side": row.camera_side,
                "diameter_mm": row.diameter_mm,
                "status": row.status,
                "confidence_score": row.confidence_score,
                "processed_at": row.processed_at.isoformat(),
                "debug_image_url": f"{rt.debug_image_base_url}/{row.measurement_id}",
            },
        )
    )
    await rt.aggregator.accept(row)


def _as_status() -> ReplayStatus:
    return ReplayStatus(
        running=_state.running,
        source_dir=_state.source_dir,
        interval_seconds=_state.interval_s,
        pairs_sent=_state.pairs_sent,
        total_pairs=_state.total_pairs,
    )
