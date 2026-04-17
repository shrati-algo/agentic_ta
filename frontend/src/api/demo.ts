import { apiClient } from "./client";

export interface ReplayStatus {
  running: boolean;
  source_dir: string | null;
  interval_seconds: number;
  pairs_sent: number;
  total_pairs: number;
}

export interface ReplayStartRequest {
  source_dir?: string;
  interval_seconds?: number;
  max_pairs?: number;
}

export async function getReplayStatus(): Promise<ReplayStatus> {
  const r = await apiClient.get<ReplayStatus>("/v1/demo/replay/status");
  return r.data;
}

export async function startReplay(
  body: ReplayStartRequest = {}
): Promise<ReplayStatus> {
  const r = await apiClient.post<ReplayStatus>("/v1/demo/replay/start", body);
  return r.data;
}

export async function stopReplay(): Promise<ReplayStatus> {
  const r = await apiClient.post<ReplayStatus>("/v1/demo/replay/stop");
  return r.data;
}
