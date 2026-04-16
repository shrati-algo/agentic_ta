"""Structured logging configuration."""

from __future__ import annotations

import hashlib
import logging
import sys

import structlog


def hash_chassis(value: str | None) -> str | None:
    """Return a short deterministic hash of *value* for non-debug logs.

    The chassis number is business-sensitive; plaintext is only
    permitted in debug logs on a developer's machine.
    """
    if value is None:
        return None
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON structlog config."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level.upper(),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)
    return logger
