"""Versioned algorithm parameter loader.

Algorithm parameters live as YAML files in ``configs/algo_params/<version>.yaml``.
They are loaded once at startup and treated as immutable.  Changing any value
requires a version bump and an ADR entry.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class CLAHEParams(BaseModel):
    clip_limit: float
    tile_grid_size: tuple[int, int]


class BlurParams(BaseModel):
    kernel: int


class CannyParams(BaseModel):
    lower_ratio: float
    upper_ratio: float


class HoughParams(BaseModel):
    dp: float
    min_dist: int
    param1: int
    param2: int
    min_radius_px: int
    max_radius_px: int


class CenterRegionParams(BaseModel):
    inner_fraction: float


class RansacParams(BaseModel):
    iterations: int
    inlier_threshold_px: float
    seed: int = 42


class ConfidenceParams(BaseModel):
    conf_pass: float
    conf_review: float


class ToleranceParams(BaseModel):
    min_mm: float
    max_mm: float
    asymmetry_threshold_mm: float


class AlgoParams(BaseModel):
    """Top-level algorithm parameter set, pinned by version string."""

    version: str
    clahe: CLAHEParams
    blur: BlurParams
    canny: CannyParams
    hough: HoughParams
    center_region: CenterRegionParams
    ransac: RansacParams
    confidence: ConfidenceParams
    tolerance: ToleranceParams


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_CONFIGS_ROOT = Path(__file__).resolve().parents[3] / "configs" / "algo_params"


def load_algo_params(version: str, *, base_dir: Path | None = None) -> AlgoParams:
    """Load and validate an algo_params YAML by version string.

    Parameters
    ----------
    version:
        The version identifier, e.g. ``"algo-1.2.0"``.
    base_dir:
        Override the directory to search in (useful for tests).

    Raises
    ------
    FileNotFoundError
        If the YAML file does not exist.
    pydantic.ValidationError
        If the YAML content does not match the schema.
    """
    root = base_dir or _CONFIGS_ROOT
    path = root / f"{version}.yaml"

    if not path.exists():
        msg = f"algo_params file not found: {path}"
        raise FileNotFoundError(msg)

    with path.open() as fh:
        raw = yaml.safe_load(fh)

    return AlgoParams.model_validate(raw)
