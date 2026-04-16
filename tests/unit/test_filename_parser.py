"""Tests for tad.data.filename_parser."""

from __future__ import annotations

import pytest

from tad.api.errors import BadFilename
from tad.data.filename_parser import ParsedName, parse_filename


class TestParseFilename:
    # ---- valid filenames --------------------------------------------------

    def test_standard_left(self) -> None:
        result = parse_filename("MALBB51BLPM123456_L.jpg")
        assert result == ParsedName(chassis_no="MALBB51BLPM123456", camera_side="L")

    def test_standard_right(self) -> None:
        result = parse_filename("MALBB51BLPM123456_R.jpg")
        assert result == ParsedName(chassis_no="MALBB51BLPM123456", camera_side="R")

    def test_jpeg_extension(self) -> None:
        result = parse_filename("MALBB51BLPM123456_L.jpeg")
        assert result.camera_side == "L"

    def test_png_extension(self) -> None:
        result = parse_filename("MALBB51BLPM123456_R.png")
        assert result.camera_side == "R"

    def test_with_sequence_number(self) -> None:
        result = parse_filename("MALBB51BLPM123456_L_001.jpg")
        assert result.chassis_no == "MALBB51BLPM123456"
        assert result.camera_side == "L"

    def test_case_insensitive_extension(self) -> None:
        result = parse_filename("MALBB51BLPM123456_L.JPG")
        assert result.camera_side == "L"

    def test_lowercase_camera_normalised(self) -> None:
        result = parse_filename("MALBB51BLPM123456_l.jpg")
        assert result.camera_side == "L"

    def test_chassis_normalised_to_uppercase(self) -> None:
        result = parse_filename("malbb51blpm123456_L.jpg")
        assert result.chassis_no == "MALBB51BLPM123456"

    def test_all_digits_chassis(self) -> None:
        result = parse_filename("12345678901234567_R.jpg")
        assert result.chassis_no == "12345678901234567"

    # ---- invalid filenames ------------------------------------------------

    def test_empty_string_raises(self) -> None:
        with pytest.raises(BadFilename, match="does not match"):
            parse_filename("")

    def test_no_camera_side_raises(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("MALBB51BLPM123456.jpg")

    def test_invalid_camera_side_raises(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("MALBB51BLPM123456_X.jpg")

    def test_short_chassis_raises(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("MALB_L.jpg")

    def test_chassis_with_forbidden_chars_raises(self) -> None:
        # VIN format: no I, O, Q
        with pytest.raises(BadFilename):
            parse_filename("MALBB51BLPM12345I_L.jpg")

    def test_chassis_with_O_raises(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("MALBB51BLPM12345O_L.jpg")

    def test_chassis_with_Q_raises(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("MALBB51BLPM12345Q_L.jpg")

    def test_unsupported_extension_raises(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("MALBB51BLPM123456_L.bmp")

    def test_no_extension_raises(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("MALBB51BLPM123456_L")

    def test_directory_path_not_accepted(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("some/dir/MALBB51BLPM123456_L.jpg")

    def test_extra_underscores_in_chassis_raises(self) -> None:
        with pytest.raises(BadFilename):
            parse_filename("MAL_B51BLPM123456_L.jpg")

    # ---- ParsedName is frozen ---------------------------------------------

    def test_parsed_name_is_frozen(self) -> None:
        result = parse_filename("MALBB51BLPM123456_L.jpg")
        with pytest.raises(AttributeError):
            result.chassis_no = "changed"  # type: ignore[misc]
