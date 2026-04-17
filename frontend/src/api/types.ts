/** TypeScript mirrors of the Pydantic schemas in src/tad/api/schemas.py. */

import type { Status, CameraSide } from "../labels";

export type { Status, CameraSide };

export type SessionStatus = "ACTIVE" | "STOPPED" | "FAILED";
export type OperatorDecision = "CORRECT" | "INCORRECT";

export interface StartRequest {
  started_by: string;
  shift?: "A" | "B" | "C" | null;
  area?: string | null;
  notes?: string | null;
}

export interface StartResponse {
  session_id: string;
  status: "ACTIVE";
  left_dir: string;
  right_dir: string;
  algo_params_version: string;
  left_calibration: string;
  right_calibration: string;
  started_at: string;
}

export interface SessionSummary {
  total: number;
  pass: number;
  review: number;
  fail: number;
  error: number;
  incomplete: number;
}

export interface StopResponse {
  session_id: string;
  status: "STOPPED";
  stopped_at: string;
  summary: SessionSummary;
}

export interface SessionInfo {
  session_id: string;
  status: SessionStatus;
  started_at: string;
  stopped_at: string | null;
  algo_params_version: string;
}

export interface ChassisListItem {
  chassis_record_id: string;
  chassis_no: string;
  overall_status: Status;
  avg_diameter_mm: number | null;
  timestamp: string;
  shift: string | null;
  area: string | null;
  flagged: boolean;
}

export interface ChassisListResponse {
  page: number;
  page_size: number;
  total: number;
  items: ChassisListItem[];
}

export interface ChassisPerCamera {
  measurement_id: string;
  diameter_mm: number | null;
  status: Status;
  confidence: number | null;
  debug_image_url: string;
}

export interface ChassisDetail {
  chassis_record_id: string;
  chassis_no: string;
  overall_status: Status;
  flagged: boolean;
  timestamp: string;
  shift: string | null;
  area: string | null;
  left: ChassisPerCamera | null;
  right: ChassisPerCamera | null;
  operator_decision: OperatorDecision | null;
}

export interface TrendPoint {
  date: string;
  review: number;
  fail: number;
}

export interface RecentAlert {
  chassis_record_id: string;
  chassis_no: string;
  timestamp: string;
  overall_status: Status;
}

export interface DashboardSummary {
  total: number;
  pass: number;
  review: number;
  fail: number;
  violation_pct: number;
  trend: TrendPoint[];
  recent_alerts: RecentAlert[];
}

export interface DecisionRequest {
  decision: OperatorDecision;
  decided_by: string;
}

export interface FlagRequest {
  flagged: boolean;
  by: string;
}

export type SseEventType =
  | "session_opened"
  | "camera_result"
  | "chassis_result"
  | "warning"
  | "session_closed";

export interface SseEvent<T = unknown> {
  type: SseEventType;
  data: T;
}

export interface ChassisResultEvent {
  chassis_record_id: string;
  chassis_no: string;
  left_diameter_mm: number | null;
  right_diameter_mm: number | null;
  avg_diameter_mm: number | null;
  asymmetry_mm: number | null;
  overall_status: Status;
  shift: string | null;
  area: string | null;
  aggregated_at: string;
}

export interface CameraResultEvent {
  measurement_id: string;
  chassis_no: string;
  camera_side: CameraSide;
  diameter_mm: number | null;
  status: Status;
  confidence_score: number | null;
  processed_at: string;
  debug_image_url: string | null;
}
