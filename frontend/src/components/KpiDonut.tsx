import { Cell, Pie, PieChart, ResponsiveContainer } from "recharts";

import { STATUS_DOT_COLOR, STATUS_LABEL } from "../labels";

interface Props {
  pass: number;
  review: number;
  fail: number;
  violationPct: number;
}

const COLOURS = ["#16a34a", "#f59e0b", "#dc2626"]; // pass, review, fail

export function KpiDonut({ pass, review, fail, violationPct }: Props) {
  const total = pass + review + fail;
  const data = [
    { name: STATUS_LABEL.PASS, value: pass },
    { name: STATUS_LABEL.REVIEW, value: review },
    { name: STATUS_LABEL.FAIL, value: fail },
  ];
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-slate-700">Violations Today</h3>
        <span className="text-xs text-slate-400">{total} total</span>
      </div>
      <div className="flex items-center gap-4">
        <div className="relative h-32 w-32 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                innerRadius={40}
                outerRadius={60}
                dataKey="value"
                paddingAngle={2}
                startAngle={90}
                endAngle={-270}
              >
                {data.map((_, i) => (
                  <Cell key={i} fill={COLOURS[i]} />
                ))}
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-lg font-bold text-slate-900">
              {violationPct.toFixed(2)}%
            </span>
            <span className="text-[10px] uppercase tracking-wide text-slate-400">
              violations
            </span>
          </div>
        </div>
        <ul className="flex flex-col gap-1.5 text-sm">
          <LegendRow label={STATUS_LABEL.PASS} count={pass} colour={STATUS_DOT_COLOR.PASS} />
          <LegendRow label={STATUS_LABEL.REVIEW} count={review} colour={STATUS_DOT_COLOR.REVIEW} />
          <LegendRow label={STATUS_LABEL.FAIL} count={fail} colour={STATUS_DOT_COLOR.FAIL} />
          <li className="mt-1 border-t border-slate-200 pt-1 text-xs text-slate-500">
            Total: <span className="font-semibold text-slate-800">{total}</span>
          </li>
        </ul>
      </div>
    </div>
  );
}

function LegendRow({
  label,
  count,
  colour,
}: {
  label: string;
  count: number;
  colour: string;
}) {
  return (
    <li className="flex items-center gap-2">
      <span className={`h-2.5 w-2.5 rounded-full ${colour}`} aria-hidden="true" />
      <span className="text-slate-600">{label}</span>
      <span className="ml-auto font-medium text-slate-900">{count}</span>
    </li>
  );
}
