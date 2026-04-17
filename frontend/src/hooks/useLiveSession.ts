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
    getActiveSession()
      .then((s) => {
        if (!cancelled) {
          setSessionId(s ? s.session_id : null);
        }
      })
      .catch(() => {
        if (!cancelled) setSessionId(null);
      });
    return () => {
      cancelled = true;
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
