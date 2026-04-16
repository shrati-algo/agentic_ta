"""Versioned algorithm parameter loader.

Algorithm parameters live as YAML files in ``configs/algo_params/<version>.yaml``.
They are loaded once at startup and treated as immutable.  Changing any value
requires a version bump and an ADR entry.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


class BlurParams(BaseModel):
    kernel: int


class ThresholdParams(BaseModel):
    """Adaptive Gaussian threshold parameters (replaces Canny in v1.3+)."""

    block_size: int
    c: int


class MorphologyParams(BaseModel):
    """Morphological close parameters applied after thresholding."""

    kernel_size: int
    iterations: int


class ContourParams(BaseModel):
    """Contour-filter parameters before masked Hough."""

    min_area: float


class HoughParams(BaseModel):
    """Hough gradient parameters (run on each contour mask)."""

    dp: float
    min_dist: int
    param1: int
    param2: int


class TargetParams(BaseModel):
    """Target diameter and radius-window used to constrain Hough."""

    diameter_mm: float
    radius_tolerance_mm: float


class ToleranceParams(BaseModel):
    """Classification bands and absolute tolerance window."""

    min_mm: float
    max_mm: float
    ok_band_mm: float
    somewhat_ok_band_mm: float
    asymmetry_threshold_mm: float


class AlgoParams(BaseModel):
    """Top-level algorithm parameter set, pinned by version string."""

    version: str
    blur: BlurParams
    threshold: ThresholdParams
    morphology: MorphologyParams
    contour: ContourParams
    hough: HoughParams
    target: TargetParams
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
        The version identifier, e.g. ``"algo-1.3.0"``.
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
