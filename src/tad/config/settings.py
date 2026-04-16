"""Application settings loaded from environment variables / .env file."""

from __future__ import annotations

import functools
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Central configuration for the TAD service.

    Loaded once at startup; treated as immutable for the lifetime of the process.
    """

    # Postgres
    db_dsn: str

    # MinIO / S3
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "tad-debug"

    # Image folders
    images_left_dir: str
    images_right_dir: str

    # Algorithm parameters
    algo_params_version: str

    # Calibration
    default_calibration_left: str
    default_calibration_right: str

    # Thresholds
    asymmetry_threshold_mm: float = 0.15

    # Queue
    queue_max_size: int = 256

    # Observability
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Auth
    auth_enabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@functools.lru_cache
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
