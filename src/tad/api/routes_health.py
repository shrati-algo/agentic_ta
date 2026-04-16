"""Liveness and readiness probes."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from tad.config.algo_params import load_algo_params
from tad.config.calibration import load_calibration
from tad.config.settings import Settings, get_settings

router = APIRouter(prefix="/v1", tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe -- always 200 if the process is running."""
    return {"status": "ok"}


@router.get("/ready")
async def ready(request: Request) -> JSONResponse:
    """Readiness probe -- 200 only when all dependencies are available.

    Checks:
    - Both calibration files load and validate.
    - Both image directories exist.
    - The configured algo_params version loads.
    - Blob store responds (if one is registered on app.state).
    """
    settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
    errors: list[str] = []

    for label, path in [
        ("left calibration", settings.default_calibration_left),
        ("right calibration", settings.default_calibration_right),
    ]:
        try:
            load_calibration(path)
        except Exception as exc:
            errors.append(f"{label}: {exc}")

    for label, dir_path in [
        ("left image dir", settings.images_left_dir),
        ("right image dir", settings.images_right_dir),
    ]:
        if not Path(dir_path).is_dir():
            errors.append(f"{label} not found: {dir_path}")

    try:
        load_algo_params(settings.algo_params_version)
    except Exception as exc:
        errors.append(f"algo_params: {exc}")

    # Blob store check (best-effort)
    blob_store = getattr(request.app.state, "blob_store", None)
    if blob_store is not None:
        try:
            await blob_store.exists("_ready_probe")
        except Exception as exc:
            errors.append(f"blob store: {exc}")

    if errors:
        return JSONResponse(status_code=503, content={"status": "not ready", "errors": errors})
    return JSONResponse(status_code=200, content={"status": "ready"})
