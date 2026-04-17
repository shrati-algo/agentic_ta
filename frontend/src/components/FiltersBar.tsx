import { Download, Search } from "lucide-react";
import { useState } from "react";

import type { Status } from "../api/types";

export interface Filters {
  quickRange: "TODAY" | "7D" | "CUSTOM";
  shift: "" | "A" | "B" | "C";
  condition: "" | Status;
  search: string;
}

interface Props {
  filters: Filters;
  onChange: (f: Filters) => void;
  onExport?: () => void;
  total: number;
}

export function FiltersBar({ filters, onChange, onExport, total }: Props) {
  const [search, setSearch] = useState(filters.search);

  return (
    <div className="flex flex-wrap items-center gap-3 border-b border-slate-200 pb-3">
      <div>
        <h2 className="text-base font-semibold text-slate-800">
          Production Details
        </h2>
        <span className="text-xs text-slate-500">{total} items</span>
      </div>

      <div className="ml-4 flex gap-1 rounded border border-slate-200 bg-white p-0.5">
        {(["TODAY", "7D", "CUSTOM"] as const).map((key) => (
          <button
            key={key}
            onClick={() => onChange({ ...filters, quickRange: key })}
            className={`rounded px-3 py-1 text-xs font-medium transition ${
              filters.quickRange === key
                ? "bg-slate-900 text-white"
                : "text-slate-600 hover:bg-slate-100"
            }`}
          >
            {key === "TODAY" ? "Today" : key === "7D" ? "Past 7 Days" : "Date Range"}
          </button>
        ))}
      </div>

      <label className="flex items-center gap-1 text-xs text-slate-500">
        Shift
        <select
          value={filters.shift}
          onChange={(e) =>
            onChange({ ...filters, shift: e.target.value as Filters["shift"] })
          }
          className="rounded border border-slate-200 bg-white px-2 py-1 text-xs"
        >
          <option value="">All</option>
          <option value="A">A</option>
          <option value="B">B</option>
          <option value="C">C</option>
        </select>
      </label>

      <label className="flex items-center gap-1 text-xs text-slate-500">
        Condition
        <select
          value={filters.condition}
          onChange={(e) =>
            onChange({
              ...filters,
              condition: e.target.value as Filters["condition"],
            })
          }
          className="rounded border border-slate-200 bg-white px-2 py-1 text-xs"
        >
          <option value="">All</option>
          <option value="PASS">Okay</option>
          <option value="REVIEW">Somewhat Okay</option>
          <option value="FAIL">Not Okay</option>
          <option value="ERROR">Error</option>
        </select>
      </label>

      <form
        className="flex items-center gap-1"
        onSubmit={(e) => {
          e.preventDefault();
          onChange({ ...filters, search });
        }}
      >
        <div className="flex items-center rounded border border-slate-200 bg-white px-2">
          <Search className="h-3.5 w-3.5 text-slate-400" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search Product ID"
            className="w-44 border-0 bg-transparent py-1 pl-1.5 text-xs focus:outline-none"
          />
        </div>
      </form>

      {onExport && (
        <button
          type="button"
          onClick={onExport}
          className="ml-auto flex items-center gap-1 rounded border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
          aria-label="Export CSV"
        >
          <Download className="h-3.5 w-3.5" />
          Export
        </button>
      )}
    </div>
  );
}
