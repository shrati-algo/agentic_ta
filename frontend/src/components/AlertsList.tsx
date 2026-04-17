import { format, parseISO } from "date-fns";
import { ArrowUpRight } from "lucide-react";
import { Link } from "react-router-dom";

import type { RecentAlert } from "../api/types";
import { ROUTES } from "../routes";
import { StatusPill } from "./StatusPill";

interface Props {
  alerts: RecentAlert[];
}

export function AlertsList({ alerts }: Props) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Recent Alerts</h3>
        <span className="text-xs text-slate-400">{alerts.length}</span>
      </div>
      {alerts.length === 0 ? (
        <p className="text-xs text-slate-400">No recent alerts.</p>
      ) : (
        <ul className="flex max-h-40 flex-col divide-y divide-slate-100 overflow-auto">
          {alerts.map((a) => (
            <li key={a.chassis_record_id}>
              <Link
                to={ROUTES.detail(a.chassis_record_id)}
                className="flex items-center gap-2 py-2 text-sm hover:bg-slate-50"
              >
                <span className="text-xs text-slate-500">
                  {safeTime(a.timestamp)}
                </span>
                <span className="truncate font-mono text-xs text-slate-700">
                  {a.chassis_no}
                </span>
                <span className="ml-auto flex items-center gap-2">
                  <StatusPill status={a.overall_status} />
                  <ArrowUpRight className="h-3.5 w-3.5 text-slate-400" />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function safeTime(iso: string): string {
  try {
    return format(parseISO(iso), "HH:mm:ss");
  } catch {
    return iso;
  }
}
