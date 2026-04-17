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
    # Comma-separated list of accepted X-Service-Token values. Only
    # consulted when auth_enabled is True. Empty = no token required
    # (even if auth_enabled). Example env:
    #     SERVICE_TOKENS="prod-token-1,prod-token-2"
    service_tokens: str = ""

    # Feature flags
    # Gate the /v1/demo/* router. Off by default so a production image
    # does not expose the replay surface; turn on in dev/demo compose
    # files with DEMO_ENABLED=true.
    demo_enabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def allowed_tokens(self) -> frozenset[str]:
        """Parse ``service_tokens`` into a frozen set of non-empty strings."""
        return frozenset(t.strip() for t in self.service_tokens.split(",") if t.strip())


@functools.lru_cache
def get_settings() -> Settings:
    """Return the cached singleton Settings instance."""
    return Settings()
