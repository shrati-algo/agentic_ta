import { apiClient } from "./client";
import type {
  SessionInfo,
  StartRequest,
  StartResponse,
  StopResponse,
} from "./types";

export async function startSession(
  body: StartRequest
): Promise<StartResponse> {
  const r = await apiClient.post<StartResponse>("/v1/sessions/start", body);
  return r.data;
}

export async function stopSession(id: string): Promise<StopResponse> {
  const r = await apiClient.post<StopResponse>(`/v1/sessions/${id}/stop`);
  return r.data;
}

export async function getActiveSession(): Promise<SessionInfo | null> {
  const r = await apiClient.get<SessionInfo[]>("/v1/sessions", {
    params: { status: "ACTIVE" },
  });
  return r.data.length ? r.data[0] : null;
}
