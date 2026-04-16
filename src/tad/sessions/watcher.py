"""Filesystem watcher that bridges ``watchdog`` into an ``asyncio.Queue``.

One instance per camera side.  ``watchdog`` runs its observer in its own
thread; we bridge events onto the event loop via
``loop.call_soon_threadsafe``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


@dataclass(frozen=True)
class QueueItem:
    side: Literal["L", "R"]
    path: Path


class _Handler(FileSystemEventHandler):
    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        queue: asyncio.Queue[QueueItem],
        side: Literal["L", "R"],
    ) -> None:
        self._loop = loop
        self._queue = queue
        self._side = side

    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        self._loop.call_soon_threadsafe(self._enqueue, QueueItem(side=self._side, path=path))

    def _enqueue(self, item: QueueItem) -> None:
        import contextlib

        # Drop on overflow; watcher must not block the observer thread
        with contextlib.suppress(asyncio.QueueFull):
            self._queue.put_nowait(item)


class FolderWatcher:
    def __init__(
        self,
        side: Literal["L", "R"],
        path: Path,
        queue: asyncio.Queue[QueueItem],
        *,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        self._side = side
        self._path = path
        self._queue = queue
        self._loop = loop or asyncio.get_event_loop()
        self._observer: Observer | None = None  # type: ignore[valid-type]

    def start(self) -> None:
        if self._observer is not None:
            return
        obs = Observer()
        obs.schedule(
            _Handler(self._loop, self._queue, self._side),
            str(self._path),
            recursive=False,
        )
        obs.start()
        self._observer = obs

    def stop(self, *, timeout: float = 5.0) -> None:
        if self._observer is None:
            return
        self._observer.stop()
        self._observer.join(timeout=timeout)
        self._observer = None
