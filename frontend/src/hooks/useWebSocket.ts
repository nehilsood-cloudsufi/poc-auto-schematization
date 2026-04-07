/**
 * Custom React hook for WebSocket connections.
 *
 * REACT CONCEPT: Callbacks passed as props change identity on every render
 * (unless memoized with useCallback). If we put them in useEffect's dependency
 * array, the effect re-runs every render → infinite reconnect loop.
 * Solution: store callbacks in refs so the effect only depends on runId.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import type { ProgressEvent } from "@/types";

interface UseWebSocketOptions {
  runId: string | null;
  enabled?: boolean;
  onEvent?: (event: ProgressEvent) => void;
  onComplete?: (event: ProgressEvent) => void;
  onError?: (event: ProgressEvent) => void;
}

export function useWebSocket({
  runId,
  enabled = true,
  onEvent,
  onComplete,
  onError,
}: UseWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  // Store callbacks in refs to avoid re-triggering the effect
  const onEventRef = useRef(onEvent);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);
  onEventRef.current = onEvent;
  onCompleteRef.current = onComplete;
  onErrorRef.current = onError;

  useEffect(() => {
    if (!runId || !enabled) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws/progress/${runId}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
    };

    ws.onmessage = (messageEvent) => {
      const event = JSON.parse(messageEvent.data as string) as ProgressEvent;
      setEvents((prev) => [...prev, event]);
      onEventRef.current?.(event);

      if (event.type === "complete") {
        onCompleteRef.current?.(event);
      } else if (event.type === "error") {
        onErrorRef.current?.(event);
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = () => {
      setConnected(false);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [runId, enabled]); // Only reconnect when runId or enabled changes

  const clearEvents = useCallback(() => setEvents([]), []);

  return { connected, events, clearEvents };
}
