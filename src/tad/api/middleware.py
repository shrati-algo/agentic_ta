"""Request-ID middleware.

Generates a short ``X-Request-Id`` if the inbound request doesn't carry
one, binds it to structlog's context vars, stores it on ``request.state``,
and echoes it back on every response.
"""

from __future__ import annotations

import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

HEADER = "X-Request-Id"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get(HEADER) or _new_request_id()
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response: Response = await call_next(request)
        response.headers[HEADER] = request_id
        return response


def _new_request_id() -> str:
    return f"rid-{uuid.uuid4().hex[:12]}"
