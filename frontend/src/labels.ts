/**
 * Single source of truth for UI terminology (TRD Section 10.3).
 * Never hard-code status strings elsewhere in the frontend.
 */

export type Status = "PASS" | "FAIL" | "REVIEW" | "ERROR";
export type CameraSide = "L" | "R";

export const STATUS_LABEL: Record<Status, string> = {
  PASS: "Okay",
  REVIEW: "Somewhat Okay",
  FAIL: "Not Okay",
  ERROR: "Error",
};

export const STATUS_COLOR: Record<Status, string> = {
  PASS: "text-green-800 bg-green-100 ring-green-200",
  REVIEW: "text-amber-800 bg-amber-100 ring-amber-200",
  FAIL: "text-red-800 bg-red-100 ring-red-200",
  ERROR: "text-gray-700 bg-gray-100 ring-gray-200",
};

export const STATUS_DOT_COLOR: Record<Status, string> = {
  PASS: "bg-green-500",
  REVIEW: "bg-amber-500",
  FAIL: "bg-red-500",
  ERROR: "bg-gray-400",
};

export const CAMERA_LABEL: Record<CameraSide, string> = {
  L: "Cam1",
  R: "Cam2",
};

export function statusLabel(status: Status): string {
  return STATUS_LABEL[status];
}

export function cameraLabel(side: CameraSide): string {
  return CAMERA_LABEL[side];
}
