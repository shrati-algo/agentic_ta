"""Tests for tad.config.algo_params."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tad.config.algo_params import load_algo_params

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "configs" / "algo_params"


class TestLoadAlgoParams:
    def test_load_valid_version(self) -> None:
        params = load_algo_params("algo-1.2.0", base_dir=CONFIGS_DIR)

        assert params.version == "algo-1.2.0"
        assert params.clahe.clip_limit == 2.0
        assert params.clahe.tile_grid_size == (8, 8)
        assert params.blur.kernel == 5
        assert params.canny.lower_ratio == 0.66
        assert params.canny.upper_ratio == 1.33
        assert params.hough.dp == 1.2
        assert params.hough.min_dist == 40
        assert params.hough.param1 == 100
        assert params.hough.param2 == 30
        assert params.hough.min_radius_px == 40
        assert params.hough.max_radius_px == 160
        assert params.center_region.inner_fraction == 0.7
        assert params.ransac.iterations == 200
        assert params.ransac.inlier_threshold_px == 1.0
        assert params.ransac.seed == 42
        assert params.confidence.conf_pass == 0.85
        assert params.confidence.conf_review == 0.60
        assert params.tolerance.min_mm == 47.0
        assert params.tolerance.max_mm == 47.5
        assert params.tolerance.asymmetry_threshold_mm == 0.15

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_algo_params("algo-99.99.99", base_dir=CONFIGS_DIR)

    def test_bad_yaml_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "algo-bad.yaml"
        bad_file.write_text("version: bad\nclahe: not_a_dict\n")

        with pytest.raises(Exception):  # noqa: B017
            load_algo_params("algo-bad", base_dir=tmp_path)

    def test_incomplete_yaml_raises(self, tmp_path: Path) -> None:
        incomplete = tmp_path / "algo-incomplete.yaml"
        incomplete.write_text(yaml.dump({"version": "algo-incomplete"}))

        with pytest.raises(Exception):  # noqa: B017
            load_algo_params("algo-incomplete", base_dir=tmp_path)
