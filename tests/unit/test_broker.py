"""Tests for tad.workers.broker."""

from __future__ import annotations

import asyncio

import pytest

from tad.workers.broker import Event, SseBroker


class TestSseBroker:
    async def test_subscribe_and_publish(self) -> None:
        broker = SseBroker()
        q = broker.subscribe()
        await broker.publish(Event(type="camera_result", payload={"k": 1}))
        evt = await asyncio.wait_for(q.get(), timeout=1.0)
        assert evt.type == "camera_result"
        assert evt.payload == {"k": 1}

    async def test_multiple_subscribers_all_receive(self) -> None:
        broker = SseBroker()
        q1 = broker.subscribe()
        q2 = broker.subscribe()
        await broker.publish(Event(type="warning", payload={"msg": "x"}))
        evt1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        evt2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert evt1.type == evt2.type == "warning"

    async def test_slow_subscriber_is_dropped(self) -> None:
        broker = SseBroker(queue_max_size=2)
        q_fast = broker.subscribe()
        q_slow = broker.subscribe()

        # Fast subscriber drains between publishes; slow one doesn't.
        for i in range(5):
            await broker.publish(Event(type="camera_result", payload={"i": i}))
            import contextlib

            with contextlib.suppress(asyncio.QueueEmpty):
                q_fast.get_nowait()

        # Slow subscriber is dropped; fast subscriber still registered.
        assert q_slow not in broker._subscribers
        assert q_fast in broker._subscribers

    async def test_unsubscribe_removes_queue(self) -> None:
        broker = SseBroker()
        q = broker.subscribe()
        assert broker.subscriber_count == 1
        broker.unsubscribe(q)
        assert broker.subscriber_count == 0

    async def test_close_marks_closed(self) -> None:
        broker = SseBroker()
        await broker.close()
        assert broker.is_closed
        with pytest.raises(RuntimeError):
            broker.subscribe()

    async def test_close_emits_session_closed(self) -> None:
        broker = SseBroker()
        q = broker.subscribe()
        await broker.close()
        evt = await asyncio.wait_for(q.get(), timeout=1.0)
        assert evt.type == "session_closed"
