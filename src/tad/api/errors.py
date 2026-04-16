"""Domain exceptions + FastAPI exception handlers.

Every TAD error maps to a structured envelope; no stack trace ever
reaches the client.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from tad.api.schemas import ErrorEnvelope

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TadError(Exception):
    """Base for all TAD domain exceptions."""

    error_code: str = "ERR_INTERNAL"
    http_status: int = 500

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class BadFilename(TadError):
    error_code = "ERR_BAD_FILENAME"
    http_status = 400


class ImageQualityError(TadError):
    error_code = "ERR_IMAGE_QUALITY"
    http_status = 400


class NoCalibrationError(TadError):
    error_code = "ERR_NO_CALIBRATION"
    http_status = 503


class SessionNotActiveError(TadError):
    error_code = "ERR_SESSION_NOT_ACTIVE"
    http_status = 404


class SessionAlreadyActiveError(TadError):
    error_code = "ERR_SESSION_ALREADY_ACTIVE"
    http_status = 409


class FolderUnavailableError(TadError):
    error_code = "ERR_FOLDER_UNAVAILABLE"
    http_status = 503


class NoCircleError(TadError):
    error_code = "ERR_NO_CIRCLE"
    http_status = 422


class ChassisNotFoundError(TadError):
    error_code = "ERR_CHASSIS_NOT_FOUND"
    http_status = 404


class MeasurementNotFoundError(TadError):
    error_code = "ERR_MEASUREMENT_NOT_FOUND"
    http_status = 404


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _env(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "rid-unknown")
    envelope = ErrorEnvelope(error_code=code, error_message=message, request_id=request_id)
    return JSONResponse(status_code=status_code, content=envelope.model_dump())


async def _tad_error_handler(request: Request, exc: TadError) -> JSONResponse:
    return _env(request, exc.error_code, exc.message, exc.http_status)


async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _env(request, "ERR_VALIDATION", str(exc.errors()), 422)


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return _env(request, "ERR_INTERNAL", "internal server error", 500)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(TadError, _tad_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _unhandled_exception_handler)
