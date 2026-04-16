"""Tests for tad.data.safe_read."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tad.data.safe_read import wait_for_stable


class TestWaitForStable:
    async def test_stable_file_returns_immediately(self, tmp_path: Path) -> None:
        f = tmp_path / "test.jpg"
        f.write_bytes(b"x" * 100)
        await wait_for_stable(f, checks=2, interval_s=0.01)
        # No exception means success

    async def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="not found"):
            await wait_for_stable(tmp_path / "nonexistent.jpg")

    async def test_growing_file_waits_until_stable(self, tmp_path: Path) -> None:
        f = tmp_path / "growing.jpg"
        f.write_bytes(b"x" * 50)

        grow_count = 0

        async def _grow() -> None:
            nonlocal grow_count
            await asyncio.sleep(0.02)
            f.write_bytes(b"x" * 100)
            grow_count += 1
            await asyncio.sleep(0.02)
            f.write_bytes(b"x" * 150)
            grow_count += 1

        task = asyncio.create_task(_grow())
        await wait_for_stable(f, checks=3, interval_s=0.03)
        await task

        # The file should have stopped growing by the time we return
        assert f.stat().st_size == 150
        assert grow_count == 2

    async def test_respects_check_count(self, tmp_path: Path) -> None:
        f = tmp_path / "stable.jpg"
        f.write_bytes(b"x" * 200)

        # With checks=1, should return after a single stable read
        await asyncio.wait_for(
            wait_for_stable(f, checks=1, interval_s=0.01),
            timeout=1.0,
        )
