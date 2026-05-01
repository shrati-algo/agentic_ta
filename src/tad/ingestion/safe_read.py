"""Size-stability protocol for safely reading images from a watched folder.

The capture system writes images to the folder, and ``watchdog`` can fire
``on_created`` before the write completes.  This module waits until the
file size stabilises before returning, preventing the pipeline from ever
seeing a truncated JPEG.
"""

from __future__ import annotations

import asyncio
from pathlib import Path


async def wait_for_stable(
    path: Path,
    *,
    checks: int = 3,
    interval_s: float = 0.15,
) -> None:
    """Wait until *path*'s size is unchanged for *checks* consecutive reads.

    Parameters
    ----------
    path:
        The file to watch.
    checks:
        Number of consecutive stable-size reads required.
    interval_s:
        Seconds to sleep between size checks.

    Raises
    ------
    FileNotFoundError
        If *path* does not exist when the first check runs.
    TimeoutError
        Not raised directly — callers should wrap this in ``asyncio.wait_for``
        if they need a hard deadline.
    """
    if not path.exists():
        msg = f"file not found: {path}"
        raise FileNotFoundError(msg)

    last_size = -1
    stable_count = 0

    while stable_count < checks:
        current_size = path.stat().st_size
        if current_size == last_size:
            stable_count += 1
        else:
            stable_count = 0
            last_size = current_size
        if stable_count < checks:
            await asyncio.sleep(interval_s)
