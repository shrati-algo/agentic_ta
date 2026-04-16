"""Per-image processing loop for an active session.

One long-running ``consumer_task`` per session reads off the shared
``asyncio.Queue`` the watchers push into, runs the full per-image
pipeline (validate -> parse -> measure via ``asyncio.to_thread`` ->
upload debug blob -> persist measurement row -> publish SSE event ->
accept into the chassis aggregator), and re-loops.

No filesystem writes happen here; everything is routed through the
``DebugImageStore`` protocol on the runtime.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from uuid import uuid4

import cv2

from tad.api.errors import BadFilename
from tad.data.filename_parser import parse_filename
from tad.data.image_validator import validate_image
from tad.data.safe_read import wait_for_stable
from tad.measurement.models import PipelineInput
from tad.measurement.pipeline import measure_innermost_diameter
from tad.persistence.models import MeasurementRow
from tad.sessions.broker import Event
from tad.sessions.runtime import SessionRuntime
from tad.sessions.watcher import QueueItem


async def consumer_loop(rt: SessionRuntime, *, stop_event: asyncio.Event) -> None:
    """Pop items off the queue until ``stop_event`` is set **and** the
    queue is drained."""
    while not stop_event.is_set() or not rt.queue.empty():
        try:
            item = await asyncio.wait_for(rt.queue.get(), timeout=0.1)
        except TimeoutError:
            continue

        try:
            await process_item(item, rt)
        except Exception as exc:
            await _emit_warning(
                rt,
                chassis_no=None,
                file=str(item.path.name),
                error_code="ERR_INTERNAL",
                message=str(exc),
            )


async def process_item(item: QueueItem, rt: SessionRuntime) -> None:
    """Drive one image through the pipeline."""
    # Idempotency — a watcher event can fire twice on some filesystems
    try:
        mtime_ns = item.path.stat().st_mtime_ns
    except FileNotFoundError:
        # File disappeared before we got to it
        return
    key = (rt.session.session_id, str(item.path.resolve()), mtime_ns)
    if key in rt.seen_items:
        return
    rt.seen_items.add(key)

    # Parse filename first — a bad name short-circuits and emits a warning
    try:
        parsed = parse_filename(item.path.name)
    except BadFilename as e:
        await _emit_warning(
            rt,
            chassis_no=None,
            file=item.path.name,
            error_code="ERR_BAD_FILENAME",
            message=str(e),
        )
        return

    # Wait for the writer to finish flushing
    try:
        await wait_for_stable(item.path, checks=2, interval_s=0.05)
    except FileNotFoundError:
        return

    data = item.path.read_bytes()
    image, vr = validate_image(data)
    if not vr.ok or image is None:
        await _emit_warning(
            rt,
            chassis_no=parsed.chassis_no,
            file=item.path.name,
            error_code=vr.error_code or "ERR_IMAGE_QUALITY",
            message=vr.message or "image validation failed",
        )
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

    t0 = time.perf_counter()
    output = await asyncio.to_thread(measure_innermost_diameter, inp)
    latency_ms = int((time.perf_counter() - t0) * 1000)

    # Upload debug image
    measurement_id = uuid4()
    debug_key = f"sessions/{rt.session.session_id}/measurements/{measurement_id}.jpg"
    ok_encode, encoded = cv2.imencode(".jpg", output.annotated_image)
    if ok_encode:
        await rt.blob_store.put(debug_key, encoded.tobytes())
    else:
        debug_key = None  # type: ignore[assignment]

    circle = output.circle
    row = MeasurementRow(
        measurement_id=measurement_id,
        session_id=rt.session.session_id,
        chassis_no=parsed.chassis_no,
        camera_side=parsed.camera_side,
        image_path=str(item.path),
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
        debug_image_key=debug_key,
        error_code=output.error_code,
        error_message=None,
        processed_at=datetime.now(UTC),
        latency_ms=latency_ms,
    )
    await rt.meas_repo.insert(row)

    # Publish per-camera result event
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
                "debug_image_url": (
                    f"{rt.debug_image_base_url}/{row.measurement_id}" if debug_key else None
                ),
            },
        )
    )

    # Feed the aggregator -- may publish a chassis_result
    await rt.aggregator.accept(row)


async def _emit_warning(
    rt: SessionRuntime,
    *,
    chassis_no: str | None,
    file: str,
    error_code: str,
    message: str,
) -> None:
    await rt.broker.publish(
        Event(
            type="warning",
            payload={
                "chassis_no": chassis_no,
                "file": file,
                "error_code": error_code,
                "message": message,
            },
        )
    )
