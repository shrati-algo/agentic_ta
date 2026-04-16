"""Camera calibration loader.

Each camera side (L / R) has an active calibration that provides the
``mm_per_px`` conversion factor.  Calibrations are stored as YAML files
in ``configs/calibration/`` and loaded at startup.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, field_validator


class Calibration(BaseModel):
    """Camera calibration record."""

    calibration_id: str
    camera_side: Literal["L", "R"]
    mm_per_px: float
    method: str
    valid_from: datetime
    operator: str
    reference_image: str

    @field_validator("camera_side", mode="before")
    @classmethod
    def _uppercase_side(cls, v: str) -> str:
        return v.upper()


def load_calibration(path: Path | str) -> Calibration:
    """Load and validate a calibration YAML file.

    Parameters
    ----------
    path:
        Absolute or relative path to the calibration YAML.

    Raises
    ------
    FileNotFoundError
        If the file does not exist.
    pydantic.ValidationError
        If the YAML content does not match the schema.
    """
    p = Path(path)

    if not p.exists():
        msg = f"calibration file not found: {p}"
        raise FileNotFoundError(msg)

    with p.open() as fh:
        raw = yaml.safe_load(fh)

    return Calibration.model_validate(raw)
