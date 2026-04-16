"""Domain exceptions mapped to API error codes.

The FastAPI exception handler (wired in ``app.py``) catches these and
returns a structured error envelope.  No stack traces ever reach the client.
"""

from __future__ import annotations


class TadError(Exception):
    """Base for all TAD domain exceptions."""

    error_code: str = "ERR_INTERNAL"

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class BadFilename(TadError):
    """Filename does not match the agreed convention (TRD Section 4.2)."""

    error_code: str = "ERR_BAD_FILENAME"


class ImageQualityError(TadError):
    """Image failed one of the quality gates (resolution, blur, exposure, integrity)."""

    error_code: str = "ERR_IMAGE_QUALITY"


class NoCalibrationError(TadError):
    """No active calibration found for the requested camera side."""

    error_code: str = "ERR_NO_CALIBRATION"


class SessionNotActiveError(TadError):
    """Operation requires an active session, but the session is not active."""

    error_code: str = "ERR_SESSION_NOT_ACTIVE"


class SessionAlreadyActiveError(TadError):
    """Attempted to start a session when one is already active."""

    error_code: str = "ERR_SESSION_ALREADY_ACTIVE"


class FolderUnavailableError(TadError):
    """One of the image folders is not reachable."""

    error_code: str = "ERR_FOLDER_UNAVAILABLE"


class NoCircleError(TadError):
    """The measurement pipeline could not detect a valid circle."""

    error_code: str = "ERR_NO_CIRCLE"
