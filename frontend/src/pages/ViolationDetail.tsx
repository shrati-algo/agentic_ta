import { ArrowLeft } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { getChassis, recordDecision, setFlagged } from "../api/chassis";
import type { ChassisDetail } from "../api/types";
import { CameraCard } from "../components/CameraCard";
import { DetailPanel } from "../components/DetailPanel";
import { Header } from "../components/Header";
import { ROUTES } from "../routes";

export function ViolationDetail() {
  const { id = "" } = useParams();
  const navigate = useNavigate();

  const [chassis, setChassis] = useState<ChassisDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    if (!id) return;
    setError(null);
    try {
      const c = await getChassis(id);
      setChassis(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [id]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const handleDecision = useCallback(
    async (decision: "CORRECT" | "INCORRECT") => {
      if (!chassis) return;
      setBusy(true);
      try {
        const updated = await recordDecision(chassis.chassis_record_id, {
          decision,
          decided_by: "operator",
        });
        setChassis(updated);
      } finally {
        setBusy(false);
      }
    },
    [chassis]
  );

  const handleFlag = useCallback(
    async (flagged: boolean) => {
      if (!chassis) return;
      setBusy(true);
      try {
        const updated = await setFlagged(chassis.chassis_record_id, {
          flagged,
          by: "operator",
        });
        setChassis(updated);
      } finally {
        setBusy(false);
      }
    },
    [chassis]
  );

  const handleDownload = useCallback(() => {
    if (!chassis) return;
    const blob = new Blob([JSON.stringify(chassis, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${chassis.chassis_no}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }, [chassis]);

  return (
    <div className="min-h-screen bg-slate-50">
      <Header />
      <main className="mx-auto max-w-7xl px-6 py-6">
        <div className="mb-4 flex items-center gap-2">
          <button
            type="button"
            onClick={() => navigate(ROUTES.home)}
            className="flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back
          </button>
          <h1 className="text-lg font-semibold text-slate-800">Violation Detail</h1>
        </div>

        {error && (
          <p className="mb-3 rounded border border-red-200 bg-red-50 p-3 text-xs text-red-700">
            {error}
          </p>
        )}

        {chassis ? (
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="flex flex-col gap-4 lg:col-span-2">
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                <CameraCard
                  side="L"
                  camera={chassis.left}
                  operatorDecision={chassis.operator_decision}
                  onDecision={handleDecision}
                  disabled={busy}
                />
                <CameraCard
                  side="R"
                  camera={chassis.right}
                  operatorDecision={chassis.operator_decision}
                  onDecision={handleDecision}
                  disabled={busy}
                />
              </div>
            </div>
            <DetailPanel
              chassis={chassis}
              onToggleFlag={handleFlag}
              onDownload={handleDownload}
            />
          </div>
        ) : (
          !error && (
            <p className="text-xs text-slate-500">Loading…</p>
          )
        )}
      </main>
    </div>
  );
}
