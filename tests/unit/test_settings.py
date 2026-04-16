"""Tests for tad.config.settings."""

from __future__ import annotations

import os
from unittest.mock import patch

from tad.config.settings import Settings


def _make_env(**overrides: str) -> dict[str, str]:
    """Return a minimal valid env dict, with optional overrides."""
    base = {
        "DB_DSN": "postgresql+psycopg://tad:tad@localhost:5432/tad",
        "MINIO_ENDPOINT": "localhost:9000",
        "MINIO_ACCESS_KEY": "minioadmin",
        "MINIO_SECRET_KEY": "minioadmin",
        "MINIO_BUCKET": "tad-debug",
        "IMAGES_LEFT_DIR": "/tmp/tad/images/left",
        "IMAGES_RIGHT_DIR": "/tmp/tad/images/right",
        "ALGO_PARAMS_VERSION": "algo-1.2.0",
        "DEFAULT_CALIBRATION_LEFT": "configs/calibration/cal-2026-03-14-L.yaml",
        "DEFAULT_CALIBRATION_RIGHT": "configs/calibration/cal-2026-03-14-R.yaml",
    }
    base.update(overrides)
    return base


class TestSettings:
    def test_loads_from_env(self) -> None:
        with patch.dict(os.environ, _make_env(), clear=True):
            s = Settings(_env_file=None)  # type: ignore[call-arg]

        assert s.db_dsn == "postgresql+psycopg://tad:tad@localhost:5432/tad"
        assert s.minio_endpoint == "localhost:9000"
        assert s.images_left_dir == "/tmp/tad/images/left"
        assert s.algo_params_version == "algo-1.2.0"

    def test_defaults(self) -> None:
        with patch.dict(os.environ, _make_env(), clear=True):
            s = Settings(_env_file=None)  # type: ignore[call-arg]

        assert s.asymmetry_threshold_mm == 0.15
        assert s.queue_max_size == 256
        assert s.log_level == "INFO"
        assert s.auth_enabled is False
        assert s.minio_bucket == "tad-debug"
