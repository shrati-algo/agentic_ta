"""Tests for tad.config.algo_params."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tad.config.algo_params import load_algo_params

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "configs" / "algo_params"


class TestLoadAlgoParams:
    def test_load_valid_version(self) -> None:
        params = load_algo_params("algo-1.3.0", base_dir=CONFIGS_DIR)

        assert params.version == "algo-1.3.0"
        assert params.blur.kernel == 5
        assert params.threshold.block_size == 51
        assert params.threshold.c == 10
        assert params.morphology.kernel_size == 3
        assert params.morphology.iterations == 1
        assert params.contour.min_area == 50.0
        assert params.hough.dp == 1.2
        assert params.hough.min_dist == 10
        assert params.hough.param1 == 50
        assert params.hough.param2 == 20
        assert params.target.diameter_mm == 47.25
        assert params.target.radius_tolerance_mm == 0.30
        assert params.tolerance.min_mm == 47.0
        assert params.tolerance.max_mm == 47.5
        assert params.tolerance.ok_band_mm == 0.20
        assert params.tolerance.somewhat_ok_band_mm == 0.50
        assert params.tolerance.asymmetry_threshold_mm == 0.15

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_algo_params("algo-99.99.99", base_dir=CONFIGS_DIR)

    def test_bad_yaml_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "algo-bad.yaml"
        bad_file.write_text("version: bad\nblur: not_a_dict\n")
        with pytest.raises(Exception):  # noqa: B017
            load_algo_params("algo-bad", base_dir=tmp_path)

    def test_incomplete_yaml_raises(self, tmp_path: Path) -> None:
        incomplete = tmp_path / "algo-incomplete.yaml"
        incomplete.write_text(yaml.dump({"version": "algo-incomplete"}))
        with pytest.raises(Exception):  # noqa: B017
            load_algo_params("algo-incomplete", base_dir=tmp_path)
