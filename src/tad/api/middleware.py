"""HTTP middleware: request-id and service-token auth."""

from __future__ import annotations

import hmac
import uuid
from collections.abc import Iterable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

HEADER = "X-Request-Id"
TOKEN_HEADER = "X-Service-Token"

# Paths that never require a service token. Health + readiness must stay
# reachable for load balancers; /docs + /openapi are developer tooling;
# the SPA root + /assets/* serve the UI which is human-operated.
_AUTH_EXEMPT_PREFIXES: tuple[str, ...] = (
    "/v1/health",
    "/v1/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/assets/",
    "/favicon",
    "/home",
)
_AUTH_EXEMPT_EXACT: frozenset[str] = frozenset({"/"})


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get(HEADER) or _new_request_id()
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response: Response = await call_next(request)
        response.headers[HEADER] = request_id
        return response


class ServiceTokenMiddleware(BaseHTTPMiddleware):
    """Compare ``X-Service-Token`` against an allowed-set in constant time.

    Only installed when ``settings.auth_enabled`` is True; if the allowed
    set is empty the middleware short-circuits to "allow all" so a
    mis-configured deploy does not lock itself out. Exempt paths (health,
    readiness, UI assets, docs, SPA routes) bypass the check so the
    dashboard and load balancers are never blocked.
    """

    def __init__(self, app, allowed: Iterable[str]):  # type: ignore[no-untyped-def]
        super().__init__(app)
        self._allowed: frozenset[str] = frozenset(allowed)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if self._allowed and not _is_exempt(request.url.path):
            provided = request.headers.get(TOKEN_HEADER, "")
            if not any(hmac.compare_digest(provided, t) for t in self._allowed):
                return JSONResponse(
                    status_code=401,
                    content={
                        "error_code": "ERR_UNAUTHORIZED",
                        "error_message": "missing or invalid X-Service-Token",
                        "request_id": getattr(request.state, "request_id", None),
                    },
                )
        return await call_next(request)


def _is_exempt(path: str) -> bool:
    if path in _AUTH_EXEMPT_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _AUTH_EXEMPT_PREFIXES)


def _new_request_id() -> str:
    return f"rid-{uuid.uuid4().hex[:12]}"
