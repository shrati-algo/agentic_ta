"""Dashboard summary route."""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query

from tad.api.deps import get_chassis_repo
from tad.api.schemas import DashboardSummary, RecentAlert, TrendPoint
from tad.persistence.repositories import ChassisRepository

router = APIRouter(prefix="/v1/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    from_ts: datetime | None = Query(default=None, alias="from"),
    to_ts: datetime | None = Query(default=None, alias="to"),
    chassis_repo: ChassisRepository = Depends(get_chassis_repo),
) -> DashboardSummary:
    now = datetime.now(UTC)
    if from_ts is None:
        from_ts = now - timedelta(days=7)
    if to_ts is None:
        to_ts = now

    rows, _ = await chassis_repo.list_page(from_ts=from_ts, to_ts=to_ts, page=1, page_size=10_000)

    pass_ = sum(1 for r in rows if r.overall_status == "PASS")
    review = sum(1 for r in rows if r.overall_status == "REVIEW")
    fail = sum(1 for r in rows if r.overall_status == "FAIL")
    total = len(rows)
    violation_pct = 100.0 * (review + fail) / total if total else 0.0

    trend_buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"review": 0, "fail": 0})
    for r in rows:
        day = r.aggregated_at.astimezone(UTC).date().isoformat()
        if r.overall_status == "REVIEW":
            trend_buckets[day]["review"] += 1
        elif r.overall_status == "FAIL":
            trend_buckets[day]["fail"] += 1
    trend = [
        TrendPoint(date=d, review=v["review"], fail=v["fail"])
        for d, v in sorted(trend_buckets.items())
    ]

    recent_alerts_rows = sorted(
        (r for r in rows if r.overall_status in ("REVIEW", "FAIL")),
        key=lambda r: r.aggregated_at,
        reverse=True,
    )[:10]
    recent_alerts = [
        RecentAlert(
            chassis_record_id=r.chassis_record_id,
            chassis_no=r.chassis_no,
            timestamp=r.aggregated_at,
            overall_status=r.overall_status,
        )
        for r in recent_alerts_rows
    ]

    return DashboardSummary.model_validate(
        {
            "total": total,
            "pass": pass_,
            "review": review,
            "fail": fail,
            "violation_pct": round(violation_pct, 2),
            "trend": [tp.model_dump() for tp in trend],
            "recent_alerts": [ra.model_dump() for ra in recent_alerts],
        }
    )
