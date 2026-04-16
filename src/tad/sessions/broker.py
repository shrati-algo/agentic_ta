"""In-memory SSE event broker with slow-subscriber drop.

Per-session fan-out: each connected dashboard gets its own bounded
queue.  If a queue fills up (slow browser, flaky network), the broker
drops that subscriber rather than back-pressuring the producer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any]


class SseBroker:
    def __init__(self, *, queue_max_size: int = 128) -> None:
        self._subscribers: list[asyncio.Queue[Event]] = []
        self._queue_max_size = queue_max_size
        self._closed = False
        self._lock = asyncio.Lock()

    def subscribe(self) -> asyncio.Queue[Event]:
        if self._closed:
            msg = "broker is closed"
            raise RuntimeError(msg)
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_max_size)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        import contextlib

        with contextlib.suppress(ValueError):
            self._subscribers.remove(q)

    async def publish(self, event: Event) -> None:
        async with self._lock:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(event)
                except asyncio.QueueFull:
                    # Drop slow subscriber — do not block producers.
                    self.unsubscribe(q)

    async def close(self) -> None:
        self._closed = True
        # Drain subscribers so any pending `.get()` wakes up with a
        # sentinel; routes handling SSE should treat `close` as "disconnect".
        for q in list(self._subscribers):
            try:
                q.put_nowait(Event(type="session_closed", payload={}))
            except asyncio.QueueFull:
                self.unsubscribe(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    @property
    def is_closed(self) -> bool:
        return self._closed
