"""FastAPI application factory.

Wires together settings, algo params, calibrations, persistence, the
session manager, middleware, exception handlers, and all routes.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from tad.api.errors import register_exception_handlers
from tad.api.middleware import RequestIdMiddleware, ServiceTokenMiddleware
from tad.api.routes_chassis import router as chassis_router
from tad.api.routes_dashboard import router as dashboard_router
from tad.api.routes_demo import router as demo_router
from tad.api.routes_health import router as health_router
from tad.api.routes_measurements import router as meas_router
from tad.api.routes_sessions import router as sessions_router
from tad.config.algo_params import AlgoParams, load_algo_params
from tad.config.calibration import Calibration, load_calibration
from tad.config.settings import Settings, get_settings
from tad.observability.logging_conf import configure_logging
from tad.persistence.blob_store import DebugImageStore, InMemoryBlobStore
from tad.persistence.repositories import (
    ChassisRepository,
    MeasurementRepository,
    SessionRepository,
)
from tad.sessions.manager import SessionManager


def create_app(
    *,
    settings: Settings | None = None,
    algo_params: AlgoParams | None = None,
    left_calibration: Calibration | None = None,
    right_calibration: Calibration | None = None,
    session_repo: SessionRepository | None = None,
    meas_repo: MeasurementRepository | None = None,
    chassis_repo: ChassisRepository | None = None,
    blob_store: DebugImageStore | None = None,
    session_manager: SessionManager | None = None,
    start_watchers: bool = True,
    run_consumer: bool = True,
) -> FastAPI:
    """Build the FastAPI app.

    In tests, the caller provides in-memory repos + blob store and may
    also supply a pre-built ``SessionManager`` (which is what
    ``routes_sessions`` and ``routes_chassis`` resolve via ``deps.py``).
    """
    if settings is None:
        settings = get_settings()
    configure_logging(settings.log_level)

    if algo_params is None:
        algo_params = load_algo_params(settings.algo_params_version)
    if left_calibration is None:
        left_calibration = load_calibration(settings.default_calibration_left)
    if right_calibration is None:
        right_calibration = load_calibration(settings.default_calibration_right)
    if blob_store is None:
        # Use the in-memory fake by default.  Plant production wires in a
        # MinIOStore instance via this kwarg.
        blob_store = InMemoryBlobStore()

    # Repositories must be supplied by the caller (production uses SQL
    # repositories over the DSN; tests use in-memory fakes).
    if session_repo is None or meas_repo is None or chassis_repo is None:
        msg = "repositories must be supplied to create_app()"
        raise ValueError(msg)

    if session_manager is None:
        session_manager = SessionManager(
            algo_params=algo_params,
            left_calibration=left_calibration,
            right_calibration=right_calibration,
            left_dir=Path(settings.images_left_dir),
            right_dir=Path(settings.images_right_dir),
            session_repo=session_repo,
            meas_repo=meas_repo,
            chassis_repo=chassis_repo,
            blob_store=blob_store,
            queue_max_size=settings.queue_max_size,
            start_watchers=start_watchers,
            run_consumer=run_consumer,
        )

    app = FastAPI(
        title="Trailing Arm Detection",
        description="Classical CV dimensional measurement service",
        version="0.1.0",
    )
    # Order matters: ServiceTokenMiddleware must run BEFORE the
    # RequestIdMiddleware so the 401 response carries a request_id we
    # bind here. Starlette runs middlewares in reverse registration
    # order, so add the auth layer first.
    if settings.auth_enabled:
        app.add_middleware(ServiceTokenMiddleware, allowed=settings.allowed_tokens())
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    # Stateful singletons on app.state (accessed by deps.py)
    app.state.settings = settings
    app.state.algo_params = algo_params
    app.state.left_calibration = left_calibration
    app.state.right_calibration = right_calibration
    app.state.session_repo = session_repo
    app.state.meas_repo = meas_repo
    app.state.chassis_repo = chassis_repo
    app.state.blob_store = blob_store
    app.state.session_manager = session_manager

    app.include_router(health_router)
    app.include_router(sessions_router)
    app.include_router(chassis_router)
    app.include_router(dashboard_router)
    app.include_router(meas_router)
    # Demo replay router is gated: production images should set
    # DEMO_ENABLED=false so the /v1/demo/* surface returns 404.
    if settings.demo_enabled:
        app.include_router(demo_router)

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """Serve ``frontend/dist/`` at the root path with SPA fallback.

    Looks for a built frontend bundle relative to the project root; if
    none exists (dev-only install), leaves the app alone so Vite can
    run on :5173 and proxy /v1/*.  Mounted *after* all API routers so
    /v1/*, /docs, and /openapi.json take precedence over the
    catch-all.
    """
    dist = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    index = dist / "index.html"
    if not index.is_file():
        return

    assets_dir = dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str) -> FileResponse:
        # API paths are handled by their routers above; anything
        # that reaches this handler is a client-side route or an
        # asset that doesn't exist in /assets (e.g. favicon).
        #
        # Guard-rail: unmounted /v1/* should surface as 404 rather
        # than the UI index -- otherwise disabling the demo router
        # (STORY-11.2) silently serves index.html to the probe.
        if full_path.startswith("v1/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404)
        candidate = dist / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


__all__ = ["create_app"]
