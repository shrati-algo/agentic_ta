import { useCallback, useEffect, useMemo, useState } from "react";

import { getDashboardSummary } from "../api/dashboard";
import { getReplayStatus, startReplay, type ReplayStatus } from "../api/demo";
import type { DashboardSummary } from "../api/types";
import { AlertsList } from "../components/AlertsList";
import { FiltersBar, type Filters } from "../components/FiltersBar";
import { Header } from "../components/Header";
import { KpiDonut } from "../components/KpiDonut";
import { KpiTrend } from "../components/KpiTrend";
import { Pagination } from "../components/Pagination";
import { ProductionTable } from "../components/ProductionTable";
import { useChassisList } from "../hooks/useChassisList";
import { useLiveSession } from "../hooks/useLiveSession";

export function Dashboard() {
  const { sessionId, connected, lastEvent } = useLiveSession();

  // Demo replay: auto-start on first Dashboard mount --------------------
  const [replay, setReplay] = useState<ReplayStatus | null>(null);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const current = await getReplayStatus();
        if (cancelled) return;
        if (current.running) {
          setReplay(current);
          return;
        }
        const started = await startReplay({ interval_seconds: 20 });
        if (!cancelled) setReplay(started);
      } catch {
        /* demo replay not available -- ignore silently */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Poll replay status every 5s so the banner stays fresh
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const s = await getReplayStatus();
        setReplay(s);
      } catch {
        /* ignore */
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Filters ------------------------------------------------------------------
  const [filters, setFilters] = useState<Filters>({
    quickRange: "7D",
    shift: "",
    condition: "",
    search: "",
  });
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);

  // Re-fetch on SSE chassis_result events
  const refreshKey = useMemo(() => {
    if (!lastEvent) return 0;
    return lastEvent.type === "chassis_result" ? lastEvent.at : 0;
  }, [lastEvent]);

  const listParams = useMemo(
    () => ({
      status: filters.condition || undefined,
      shift: filters.shift || undefined,
      search: filters.search || undefined,
      page,
      page_size: pageSize,
    }),
    [filters, page, pageSize]
  );

  const { data: list, loading, error } = useChassisList(listParams, refreshKey);

  // Dashboard summary -------------------------------------------------------
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const fetchSummary = useCallback(async () => {
    try {
      const s = await getDashboardSummary();
      setSummary(s);
    } catch {
      /* swallow -- dashboard degrades gracefully */
    }
  }, []);

  useEffect(() => {
    void fetchSummary();
  }, [fetchSummary, refreshKey]);

  const total = list?.total ?? 0;

  return (
    <div className="min-h-screen bg-slate-50">
      <Header connected={connected} sessionId={sessionId} />
      <main className="mx-auto max-w-7xl px-6 py-6">
        {replay && replay.total_pairs > 0 && (
          <div className="mb-4 flex items-center justify-between rounded-lg border border-blue-200 bg-blue-50 px-4 py-2 text-xs">
            <span className="text-blue-900">
              <span className="font-semibold">Demo replay:</span>{" "}
              {replay.running ? "streaming" : "complete"} —{" "}
              {replay.pairs_sent} / {replay.total_pairs} chassis sent at{" "}
              {replay.interval_seconds}s intervals
            </span>
            {replay.running && (
              <span className="flex items-center gap-1 text-blue-600">
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-blue-500" />
                live
              </span>
            )}
          </div>
        )}

        {/* KPI row */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <KpiDonut
            pass={summary?.pass ?? 0}
            review={summary?.review ?? 0}
            fail={summary?.fail ?? 0}
            violationPct={summary?.violation_pct ?? 0}
          />
          <KpiTrend trend={summary?.trend ?? []} />
          <AlertsList alerts={summary?.recent_alerts ?? []} />
        </div>

        {/* Production details */}
        <section className="mt-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <FiltersBar
            filters={filters}
            onChange={(f) => {
              setFilters(f);
              setPage(1);
            }}
            total={total}
            onExport={() => {
              window.location.href = "/v1/chassis?format=csv";
            }}
          />
          {error && (
            <p className="py-2 text-xs text-red-600">Failed to load: {error}</p>
          )}
          <ProductionTable items={list?.items ?? []} loading={loading} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={setPage}
            onPageSizeChange={(s) => {
              setPageSize(s);
              setPage(1);
            }}
          />
        </section>
      </main>
    </div>
  );
}
