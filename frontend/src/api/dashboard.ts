import { apiClient } from "./client";
import type { DashboardSummary } from "./types";

export async function getDashboardSummary(params?: {
  from?: string;
  to?: string;
}): Promise<DashboardSummary> {
  const r = await apiClient.get<DashboardSummary>("/v1/dashboard/summary", {
    params,
  });
  return r.data;
}
