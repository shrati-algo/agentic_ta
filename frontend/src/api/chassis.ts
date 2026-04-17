import { apiClient } from "./client";
import type {
  ChassisDetail,
  ChassisListResponse,
  DecisionRequest,
  FlagRequest,
  Status,
} from "./types";

export interface ChassisListParams {
  from?: string;
  to?: string;
  status?: Status;
  shift?: string;
  search?: string;
  page?: number;
  page_size?: number;
}

export async function listChassis(
  params: ChassisListParams = {}
): Promise<ChassisListResponse> {
  const r = await apiClient.get<ChassisListResponse>("/v1/chassis", { params });
  return r.data;
}

export async function getChassis(id: string): Promise<ChassisDetail> {
  const r = await apiClient.get<ChassisDetail>(`/v1/chassis/${id}`);
  return r.data;
}

export async function recordDecision(
  id: string,
  body: DecisionRequest
): Promise<ChassisDetail> {
  const r = await apiClient.post<ChassisDetail>(
    `/v1/chassis/${id}/decision`,
    body
  );
  return r.data;
}

export async function setFlagged(
  id: string,
  body: FlagRequest
): Promise<ChassisDetail> {
  const r = await apiClient.post<ChassisDetail>(`/v1/chassis/${id}/flag`, body);
  return r.data;
}
