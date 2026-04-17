import { useEffect, useState } from "react";

import { getActiveSession } from "../api/sessions";
import { subscribeToSession } from "../api/sse";
import type { SseEventType } from "../api/types";

interface LiveEvent {
  type: SseEventType;
  data: unknown;
  at: number;
}

interface LiveSessionState {
  sessionId: string | null;
  connected: boolean;
  lastEvent: LiveEvent | null;
}

/**
 * Discovers the current ACTIVE session on mount, subscribes to its SSE
 * event stream, and re-exposes the most recent event so consumers
 * (Dashboard) can refetch on invalidation.
 */
export function useLiveSession(): LiveSessionState {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<LiveEvent | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    // Poll /v1/sessions?status=ACTIVE until we find a session, then stop.
    // The Dashboard kicks off the demo replay (and therefore creates the
    // session) after mount, so the very first probe often returns null --
    // before this retry loop the SSE subscription never attached and the
    // UI could only refresh via a hard reload. With the retry the
    // subscription attaches as soon as the session exists.
    const probe = async (): Promise<void> => {
      try {
        const s = await getActiveSession();
        if (cancelled) return;
        if (s) {
          setSessionId(s.session_id);
          if (timer) {
            clearInterval(timer);
            timer = null;
          }
        }
      } catch {
        /* swallow -- try again on next tick */
      }
    };

    void probe();
    timer = setInterval(probe, 2000);

    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    const unsubscribe = subscribeToSession(
      sessionId,
      (type, data) => {
        setLastEvent({ type, data, at: Date.now() });
      },
      setConnected
    );
    return () => {
      unsubscribe();
      setConnected(false);
    };
  }, [sessionId]);

  return { sessionId, connected, lastEvent };
}
