/**
 * Custom React hook for WebSocket connections with auto-reconnect.
 */
import { useEffect, useRef, useState, useCallback } from "react";
import type { ProgressEvent } from "@/types";

interface UseWebSocketOptions {
  runId: string | null;
  onEvent?: (event: ProgressEvent) => void;
  onComplete?: (event: ProgressEvent) => void;
  onError?: (event: ProgressEvent) => void;
}

export function useWebSocket({ runId, onEvent, onComplete, onError }: UseWebSocketOptions) {
  const [connected, setConnected] = useState(false);
  const [events, setEvents] = useState<ProgressEvent[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  const connect = useCallback(() => {
    if (!runId) return;

    // Build WebSocket URL relative to current host
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
      onEvent?.(event);

      if (event.type === "complete") {
        onComplete?.(event);
      } else if (event.type === "error") {
        onError?.(event);
      }
    };

    ws.onclose = () => {
      setConnected(false);
    };

    ws.onerror = () => {
      setConnected(false);
    };
  }, [runId, onEvent, onComplete, onError]);

  // Connect when runId changes
  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      wsRef.current = null;
    };
  }, [connect]);

  const clearEvents = useCallback(() => setEvents([]), []);

  return { connected, events, clearEvents };
}
