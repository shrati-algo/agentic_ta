import { afterEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../src/api/client";
import { listChassis } from "../../src/api/chassis";
import { getDashboardSummary } from "../../src/api/dashboard";

describe("api client", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("listChassis hits /v1/chassis with params", async () => {
    const spy = vi
      .spyOn(apiClient, "get")
      .mockResolvedValue({ data: { page: 1, page_size: 10, total: 0, items: [] } });

    const result = await listChassis({ status: "REVIEW", page: 2, page_size: 25 });

    expect(spy).toHaveBeenCalledWith("/v1/chassis", {
      params: { status: "REVIEW", page: 2, page_size: 25 },
    });
    expect(result.items).toEqual([]);
  });

  it("getDashboardSummary hits /v1/dashboard/summary", async () => {
    const spy = vi.spyOn(apiClient, "get").mockResolvedValue({
      data: {
        total: 0,
        pass: 0,
        review: 0,
        fail: 0,
        violation_pct: 0,
        trend: [],
        recent_alerts: [],
      },
    });

    await getDashboardSummary();
    expect(spy).toHaveBeenCalledWith("/v1/dashboard/summary", { params: undefined });
  });
});
