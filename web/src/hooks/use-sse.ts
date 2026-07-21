"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { OperationEvent } from "@/lib/sse";

export type SSEState = "connecting" | "connected" | "reconnecting" | "disconnected" | "error";

/**
 * Hook for SSE with automatic reconnection, duplicate event detection, and state tracking.
 */
export function useSSE(
  url: string | null,
  onEvent: (event: OperationEvent) => void,
  options: {
    maxReconnectAttempts?: number;
    reconnectIntervalMs?: number;
    lastEventId?: string;
    onFallback?: () => void;
  } = {},
) {
  const {
    maxReconnectAttempts = 10,
    reconnectIntervalMs = 1000,
    lastEventId,
    onFallback,
  } = options;

  const [internalState, setInternalState] = useState<SSEState>("disconnected");
  const [retryCount, setRetryCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const seenIdsRef = useRef<Set<string>>(new Set());
  const retryCountRef = useRef(0);

  const onEventRef = useRef(onEvent);
  const maxAttemptsRef = useRef(maxReconnectAttempts);
  const intervalRef = useRef(reconnectIntervalMs);
  const onFallbackRef = useRef(onFallback);

  useEffect(() => { onEventRef.current = onEvent; }, [onEvent]);
  useEffect(() => { maxAttemptsRef.current = maxReconnectAttempts; }, [maxReconnectAttempts]);
  useEffect(() => { intervalRef.current = reconnectIntervalMs; }, [reconnectIntervalMs]);
  useEffect(() => { onFallbackRef.current = onFallback; }, [onFallback]);

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close();
    eventSourceRef.current = null;
    setInternalState("disconnected");
  }, []);

  useEffect(() => {
    if (!url) return;

    let cancelled = false;

    function connect(attempt: number) {
      if (cancelled) return;

      const target = new URL(url, window.location.origin);
      if (lastEventId) target.searchParams.set("last_event_id", lastEventId);

      setInternalState("connecting");
      const source = new EventSource(target);
      eventSourceRef.current = source;

      source.onopen = () => {
        if (cancelled) return;
        setInternalState("connected");
        retryCountRef.current = 0;
        setRetryCount(0);
      };

      source.onmessage = (message) => {
        if (cancelled) return;
        const eventId = message.lastEventId;
        if (eventId && seenIdsRef.current.has(eventId)) return;
        if (eventId) seenIdsRef.current.add(eventId);

        onEventRef.current({
          id: eventId,
          type: message.type,
          data: JSON.parse(message.data),
        });
      };

      source.onerror = () => {
        if (cancelled) return;
        source.close();
        const nextRetry = attempt + 1;
        retryCountRef.current = nextRetry;
        setRetryCount(nextRetry);

        if (nextRetry >= maxAttemptsRef.current) {
          setInternalState("error");
          onFallbackRef.current?.();
          return;
        }

        setInternalState("reconnecting");
        setTimeout(() => connect(nextRetry), intervalRef.current * Math.min(nextRetry, 5));
      };
    }

    connect(0);

    return () => {
      cancelled = true;
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, [url, lastEventId]);

  const state: SSEState = url ? internalState : "disconnected";

  return { state, retryCount, disconnect };
}
