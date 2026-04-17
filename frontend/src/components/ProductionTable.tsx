import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
} from "@tanstack/react-table";
import { format, parseISO } from "date-fns";
import { Flag } from "lucide-react";
import { useNavigate } from "react-router-dom";

import type { ChassisListItem } from "../api/types";
import { ROUTES } from "../routes";
import { StatusPill } from "./StatusPill";

const columns: ColumnDef<ChassisListItem>[] = [
  {
    accessorKey: "overall_status",
    header: "Overall Condition",
    cell: ({ row }) => (
      <div className="flex items-center gap-2">
        <StatusPill status={row.original.overall_status} />
        {row.original.flagged && (
          <Flag className="h-3.5 w-3.5 text-red-500" aria-label="flagged" />
        )}
      </div>
    ),
  },
  {
    accessorKey: "timestamp",
    header: "Timestamp",
    cell: ({ getValue }) => (
      <span className="text-xs text-slate-600">
        {safeFormat(getValue<string>())}
      </span>
    ),
  },
  {
    accessorKey: "chassis_no",
    header: "Product ID",
    cell: ({ getValue }) => (
      <span className="font-mono text-xs">{getValue<string>()}</span>
    ),
  },
  { accessorKey: "shift", header: "Shift" },
  { accessorKey: "area", header: "Area" },
];

interface Props {
  items: ChassisListItem[];
  loading?: boolean;
}

export function ProductionTable({ items, loading = false }: Props) {
  const navigate = useNavigate();
  const table = useReactTable({
    data: items,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-slate-200">
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <th
                  key={h.id}
                  className="px-3 py-2 text-left text-xs font-medium uppercase tracking-wide text-slate-500"
                >
                  {flexRender(h.column.columnDef.header, h.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody className="divide-y divide-slate-100 bg-white">
          {loading && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-xs text-slate-400">
                Loading…
              </td>
            </tr>
          )}
          {!loading && items.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-3 py-6 text-center text-xs text-slate-400">
                Waiting for the first chassis.
              </td>
            </tr>
          )}
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              onClick={() => navigate(ROUTES.detail(row.original.chassis_record_id))}
              className="cursor-pointer hover:bg-slate-50"
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id} className="whitespace-nowrap px-3 py-2 text-sm">
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
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
