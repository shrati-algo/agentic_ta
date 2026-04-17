import type { SseEventType } from "./types";

/** Subscribe to the per-session event stream.  Returns an `unsubscribe` callback. */
export function subscribeToSession(
  sessionId: string,
  onEvent: (type: SseEventType, data: unknown) => void,
  onStatusChange?: (connected: boolean) => void
): () => void {
  const url = `/v1/sessions/${sessionId}/events`;
  const es = new EventSource(url);

  es.onopen = () => onStatusChange?.(true);
  es.onerror = () => onStatusChange?.(false);

  const handler = (type: SseEventType) => (e: MessageEvent) => {
    try {
      onEvent(type, JSON.parse(e.data));
    } catch {
      onEvent(type, e.data);
    }
  };

  const types: SseEventType[] = [
    "session_opened",
    "camera_result",
    "chassis_result",
    "warning",
    "session_closed",
  ];
  for (const t of types) {
    es.addEventListener(t, handler(t));
  }

  return () => {
    es.close();
    onStatusChange?.(false);
  };
}
