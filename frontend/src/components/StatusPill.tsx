import { AlertTriangle, CheckCircle2, HelpCircle, XCircle } from "lucide-react";

import { STATUS_COLOR, STATUS_LABEL, type Status } from "../labels";

const ICONS: Record<Status, React.ElementType> = {
  PASS: CheckCircle2,
  REVIEW: HelpCircle,
  FAIL: XCircle,
  ERROR: AlertTriangle,
};

interface Props {
  status: Status;
  className?: string;
}

export function StatusPill({ status, className = "" }: Props) {
  const Icon = ICONS[status];
  return (
    <span
      role="status"
      aria-label={STATUS_LABEL[status]}
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${STATUS_COLOR[status]} ${className}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {STATUS_LABEL[status]}
    </span>
  );
}
