import { Maximize2 } from "lucide-react";

import type { ChassisPerCamera } from "../api/types";
import { CAMERA_LABEL, STATUS_LABEL, type CameraSide } from "../labels";
import { StatusPill } from "./StatusPill";

interface Props {
  side: CameraSide;
  camera: ChassisPerCamera | null;
  operatorDecision: "CORRECT" | "INCORRECT" | null;
  onDecision: (decision: "CORRECT" | "INCORRECT") => void;
  disabled?: boolean;
}

export function CameraCard({
  side,
  camera,
  operatorDecision,
  onDecision,
  disabled = false,
}: Props) {
  return (
    <div className="flex flex-col rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2 text-sm">
        <span className="font-semibold text-slate-700">{CAMERA_LABEL[side]}</span>
        {camera && (
          <span className="text-xs text-slate-500">
            Violation ID: <span className="font-mono">{camera.measurement_id.slice(0, 8)}</span>
          </span>
        )}
        <button
          type="button"
          className="rounded p-1 text-slate-400 hover:bg-slate-100"
          aria-label="maximise"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
      </div>

      <div className="relative aspect-[4/3] bg-slate-900">
        {camera ? (
          <img
            src={camera.debug_image_url}
            alt={`${CAMERA_LABEL[side]} debug`}
            className="h-full w-full object-contain"
            loading="lazy"
            onError={(e) => {
              (e.target as HTMLImageElement).alt = "Image unavailable";
            }}
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center text-xs text-slate-400">
            No image for {CAMERA_LABEL[side]}
          </div>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2 text-sm">
        <span className="text-slate-500">Condition</span>
        {camera ? (
          <span className="flex items-center gap-2">
            <StatusPill status={camera.status} />
            {camera.diameter_mm !== null && (
              <span className="text-xs text-slate-500">
                {camera.diameter_mm.toFixed(3)} mm
              </span>
            )}
          </span>
        ) : (
          <span className="text-xs text-slate-400">—</span>
        )}
      </div>

      <div className="flex gap-2 border-t border-slate-100 p-3">
        <button
          type="button"
          disabled={disabled || !camera}
          onClick={() => onDecision("INCORRECT")}
          className={`flex-1 rounded-md border px-3 py-1.5 text-xs font-medium transition ${
            operatorDecision === "INCORRECT"
              ? "border-slate-900 bg-slate-900 text-white"
              : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
          } disabled:cursor-not-allowed disabled:opacity-40`}
        >
          Incorrect Violation
        </button>
        <button
          type="button"
          disabled={disabled || !camera}
          onClick={() => onDecision("CORRECT")}
          className={`flex-1 rounded-md border px-3 py-1.5 text-xs font-medium transition ${
            operatorDecision === "CORRECT"
              ? "border-green-700 bg-green-600 text-white"
              : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
          } disabled:cursor-not-allowed disabled:opacity-40`}
        >
          Correct Violation
        </button>
      </div>

      <span className="sr-only">
        {camera ? `Status: ${STATUS_LABEL[camera.status]}` : "No measurement"}
      </span>
    </div>
  );
}
