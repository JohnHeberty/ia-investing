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

  const [state, setState] = useState<SSEState>("disconnected");
  const [retryCount, setRetryCount] = useState(0);
  const eventSourceRef = useRef<EventSource | null>(null);
  const seenIdsRef = useRef<Set<string>>(new Set());
  const onEventRef = useRef(onEvent);
  onEventRef.current = onEvent;
  const maxAttemptsRef = useRef(maxReconnectAttempts);
  maxAttemptsRef.current = maxReconnectAttempts;
  const intervalRef = useRef(reconnectIntervalMs);
  intervalRef.current = reconnectIntervalMs;
  const onFallbackRef = useRef(onFallback);
  onFallbackRef.current = onFallback;
  const retryCountRef = useRef(0);

  const connect = useCallback(() => {
    if (!url) {
      setState("disconnected");
      return;
    }

    const target = new URL(url, window.location.origin);
    if (lastEventId) target.searchParams.set("last_event_id", lastEventId);

    setState("connecting");
    const source = new EventSource(target);
    eventSourceRef.current = source;

    source.onopen = () => {
      setState("connected");
      retryCountRef.current = 0;
      setRetryCount(0);
    };

    source.onmessage = (message) => {
      const eventId = message.lastEventId;
      // Deduplicate events
      if (eventId && seenIdsRef.current.has(eventId)) return;
      if (eventId) seenIdsRef.current.add(eventId);

      onEventRef.current({
        id: eventId,
        type: message.type,
        data: JSON.parse(message.data),
      });
    };

    source.onerror = () => {
      source.close();
      const nextRetry = retryCountRef.current + 1;
      retryCountRef.current = nextRetry;
      setRetryCount(nextRetry);

      if (nextRetry >= maxAttemptsRef.current) {
        setState("error");
        onFallbackRef.current?.();
        return;
      }

      setState("reconnecting");
      setTimeout(() => {
        connect();
      }, intervalRef.current * Math.min(nextRetry, 5));
    };
  }, [url, lastEventId]);

  useEffect(() => {
    connect();
    return () => {
      eventSourceRef.current?.close();
    };
  }, [connect]);

  const disconnect = useCallback(() => {
    eventSourceRef.current?.close();
    setState("disconnected");
  }, []);

  return { state, retryCount, disconnect };
}
