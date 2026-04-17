import { useCallback, useEffect, useState } from "react";

import { listChassis, type ChassisListParams } from "../api/chassis";
import type { ChassisListResponse } from "../api/types";

interface State {
  data: ChassisListResponse | null;
  loading: boolean;
  error: string | null;
}

export function useChassisList(params: ChassisListParams, refreshKey: number = 0) {
  const [state, setState] = useState<State>({ data: null, loading: true, error: null });

  const fetch = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await listChassis(params);
      setState({ data, loading: false, error: null });
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setState({ data: null, loading: false, error: msg });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [JSON.stringify(params), refreshKey]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { ...state, reload: fetch };
}
