"""Uvicorn entrypoint for the Trailing Arm Detection service."""

from fastapi import FastAPI

from tad.api.routes_health import router as health_router


def create_app() -> FastAPI:
    application = FastAPI(
        title="Trailing Arm Detection",
        description="Classical CV dimensional measurement service",
        version="0.1.0",
    )
    application.include_router(health_router)
    return application


app = create_app()
