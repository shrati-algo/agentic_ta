"""Shared fixtures for unit tests."""

from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"
CALIBRATION_FIXTURES = FIXTURES_DIR / "calibration"
