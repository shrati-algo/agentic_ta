"""Tests for tad.config.calibration."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from tad.config.calibration import load_calibration

CONFIGS_DIR = Path(__file__).resolve().parents[2] / "configs" / "calibration"


class TestLoadCalibration:
    def test_load_left_calibration(self) -> None:
        cal = load_calibration(CONFIGS_DIR / "cal-2026-03-14-L.yaml")

        assert cal.calibration_id == "cal-2026-03-14-L"
        assert cal.camera_side == "L"
        assert cal.mm_per_px == pytest.approx(0.082340)
        assert cal.method == "checkerboard"
        assert cal.operator == "qa-technician-12"

    def test_load_right_calibration(self) -> None:
        cal = load_calibration(CONFIGS_DIR / "cal-2026-03-14-R.yaml")

        assert cal.calibration_id == "cal-2026-03-14-R"
        assert cal.camera_side == "R"
        assert cal.mm_per_px == pytest.approx(0.082340)

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            load_calibration("nonexistent/cal.yaml")

    def test_bad_yaml_raises(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "cal-bad.yaml"
        bad_file.write_text("calibration_id: bad\ncamera_side: L\n")

        with pytest.raises(Exception):  # noqa: B017
            load_calibration(bad_file)

    def test_camera_side_normalised_to_uppercase(self, tmp_path: Path) -> None:
        cal_file = tmp_path / "cal-lower.yaml"
        cal_data = {
            "calibration_id": "cal-lower",
            "camera_side": "l",
            "mm_per_px": 0.08,
            "method": "checkerboard",
            "valid_from": "2026-01-01T00:00:00Z",
            "operator": "test",
            "reference_image": "test.jpg",
        }
        cal_file.write_text(yaml.dump(cal_data))

        cal = load_calibration(cal_file)
        assert cal.camera_side == "L"

    def test_invalid_camera_side_raises(self, tmp_path: Path) -> None:
        cal_file = tmp_path / "cal-invalid.yaml"
        cal_data = {
            "calibration_id": "cal-invalid",
            "camera_side": "X",
            "mm_per_px": 0.08,
            "method": "checkerboard",
            "valid_from": "2026-01-01T00:00:00Z",
            "operator": "test",
            "reference_image": "test.jpg",
        }
        cal_file.write_text(yaml.dump(cal_data))

        with pytest.raises(Exception):  # noqa: B017
            load_calibration(cal_file)
