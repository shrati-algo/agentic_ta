import { useCallback, useEffect, useMemo, useState } from "react";

import { getDashboardSummary } from "../api/dashboard";
import { getReplayStatus, startReplay } from "../api/demo";
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

  // Demo replay: auto-start on first Dashboard mount so the table
  // populates without manual curl calls. The user-visible banner
  // was removed -- replay still runs silently in the background.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const current = await getReplayStatus();
        if (cancelled || current.running) return;
        await startReplay({ interval_seconds: 20 });
      } catch {
        /* demo replay not available -- ignore silently */
      }
    })();
    return () => {
      cancelled = true;
    };
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

  // Fallback poll: bump every 5s so the table + KPIs refresh even if
  // the SSE stream is still reconnecting or the initial session probe
  // hadn't landed yet. SSE events still trigger an immediate refresh
  // via `lastEvent`; this just prevents staleness when SSE is silent.
  const [pollTick, setPollTick] = useState(0);
  useEffect(() => {
    const iv = setInterval(() => setPollTick((n) => n + 1), 5000);
    return () => clearInterval(iv);
  }, []);

  // Re-fetch on SSE chassis_result events OR the 5s poll tick.
  const refreshKey = useMemo(() => {
    const sseAt =
      lastEvent && lastEvent.type === "chassis_result" ? lastEvent.at : 0;
    // Combine both so either source invalidates the memo.
    return sseAt + pollTick;
  }, [lastEvent, pollTick]);

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
