"""Per-session runtime state.

Holds everything needed to process an image for one active session:
repositories, blob store, aggregator, broker, queue, watchers, and the
cached algo_params + calibrations.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID

from tad.config.algo_params import AlgoParams
from tad.config.calibration import Calibration
from tad.persistence.blob_store import DebugImageStore
from tad.persistence.models import SessionRow
from tad.persistence.repositories import (
    ChassisRepository,
    MeasurementRepository,
    SessionRepository,
)
from tad.workers.aggregator import Aggregator
from tad.workers.broker import SseBroker

if TYPE_CHECKING:
    from tad.workers.watcher import FolderWatcher, QueueItem
else:
    QueueItem = "QueueItem"  # type: ignore[assignment]
    FolderWatcher = "FolderWatcher"  # type: ignore[assignment]


@dataclass
class SessionRuntime:
    session: SessionRow
    algo_params: AlgoParams
    calibrations: dict[str, Calibration]  # keyed by "L" / "R"
    queue: asyncio.Queue[QueueItem]
    broker: SseBroker
    aggregator: Aggregator
    meas_repo: MeasurementRepository
    chassis_repo: ChassisRepository
    session_repo: SessionRepository
    blob_store: DebugImageStore
    debug_image_base_url: str = "/v1/debug"
    watchers: list[FolderWatcher] = field(default_factory=list)
    consumer_task: asyncio.Task[None] | None = None
    seen_items: set[tuple[UUID, str, int]] = field(default_factory=set)
