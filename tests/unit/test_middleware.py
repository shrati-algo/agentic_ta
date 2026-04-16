"""Tests for request-ID middleware + error envelope."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tad.api.errors import TadError, register_exception_handlers
from tad.api.middleware import RequestIdMiddleware


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIdMiddleware)
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> dict[str, str]:
        raise TadError("deliberate failure")

    @app.get("/ok")
    async def ok() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestRequestId:
    def test_generates_when_missing(self) -> None:
        client = TestClient(_make_app())
        r = client.get("/ok")
        assert r.status_code == 200
        assert r.headers["X-Request-Id"].startswith("rid-")

    def test_echoes_when_provided(self) -> None:
        client = TestClient(_make_app())
        r = client.get("/ok", headers={"X-Request-Id": "rid-supplied"})
        assert r.headers["X-Request-Id"] == "rid-supplied"


class TestErrorEnvelope:
    def test_tad_error_maps_to_envelope(self) -> None:
        client = TestClient(_make_app(), raise_server_exceptions=False)
        r = client.get("/boom")
        assert r.status_code == 500
        body = r.json()
        assert body["error_code"] == "ERR_INTERNAL"
        assert body["error_message"] == "deliberate failure"
        assert body["request_id"].startswith("rid-")

    def test_validation_error_envelope(self) -> None:
        app = _make_app()

        @app.get("/typed")
        async def typed(x: int) -> dict[str, int]:
            return {"x": x}

        client = TestClient(app)
        r = client.get("/typed?x=not-an-int")
        assert r.status_code == 422
        assert r.json()["error_code"] == "ERR_VALIDATION"
