import { format, parseISO } from "date-fns";
import { Download, Flag } from "lucide-react";

import type { ChassisDetail } from "../api/types";
import { STATUS_LABEL } from "../labels";
import { StatusPill } from "./StatusPill";

interface Props {
  chassis: ChassisDetail;
  onToggleFlag: (flagged: boolean) => void;
  onDownload: () => void;
}

export function DetailPanel({ chassis, onToggleFlag, onDownload }: Props) {
  return (
    <aside className="flex flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
        <h3 className="text-sm font-semibold text-slate-700">Violation Detail</h3>
        <div className="flex gap-1">
          <button
            type="button"
            onClick={() => onToggleFlag(!chassis.flagged)}
            className={`flex items-center gap-1 rounded border px-2 py-1 text-xs ${
              chassis.flagged
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            }`}
            aria-pressed={chassis.flagged}
          >
            <Flag className="h-3 w-3" />
            {chassis.flagged ? "Flagged" : "Flag"}
          </button>
          <button
            type="button"
            onClick={onDownload}
            className="flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            <Download className="h-3 w-3" />
            Download
          </button>
        </div>
      </div>
      <dl className="flex flex-col divide-y divide-slate-100 text-sm">
        <Row label="Product ID">
          <span className="font-mono text-xs">{chassis.chassis_no}</span>
        </Row>
        <Row label="Overall Condition">
          <StatusPill status={chassis.overall_status} />
        </Row>
        <Row label="Timestamp">
          <span className="text-xs">{safeFormat(chassis.timestamp)}</span>
        </Row>
        <Row label="Shift">{chassis.shift ?? "—"}</Row>
        <Row label="Area">{chassis.area ?? "—"}</Row>
        {chassis.operator_decision && (
          <Row label="Operator Decision">
            <span className="text-xs">
              {chassis.operator_decision === "CORRECT"
                ? `Confirmed ${STATUS_LABEL[chassis.overall_status]}`
                : "Overridden"}
            </span>
          </Row>
        )}
      </dl>
    </aside>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between px-4 py-2">
      <dt className="text-xs uppercase tracking-wide text-slate-500">{label}</dt>
      <dd className="text-slate-700">{children}</dd>
    </div>
  );
}

function safeFormat(iso: string): string {
  try {
    return format(parseISO(iso), "dd/MM/yyyy HH:mm:ss");
  } catch {
    return iso;
  }
}
