import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { useSSE, type SSEState } from "@/hooks/use-sse";

class MockEventSource {
  static instances: MockEventSource[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  close = vi.fn();
  constructor(url: string | URL) {
    this.url = String(url);
    MockEventSource.instances.push(this);
  }
}

afterEach(() => {
  MockEventSource.instances = [];
  vi.restoreAllMocks();
  vi.useRealTimers();
});

describe("useSSE hook", () => {
  it("starts in disconnected state when no URL provided", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const { result } = renderHook(() => useSSE(null, vi.fn()));
    expect(result.current.state).toBe("disconnected");
  });

  it("transitions to connecting then connected on successful open", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    vi.useFakeTimers();

    const { result } = renderHook(() => useSSE("/api/events", vi.fn()));

    expect(result.current.state).toBe("connecting");

    act(() => {
      MockEventSource.instances[0].onopen?.();
    });

    expect(result.current.state).toBe("connected");
  });

  it("calls onEvent callback with parsed message data", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const onEvent = vi.fn();

    renderHook(() => useSSE("/api/events", onEvent));

    act(() => {
      MockEventSource.instances[0].onmessage?.({
        lastEventId: "evt-1",
        type: "message",
        data: '{"status":"running"}',
      } as MessageEvent);
    });

    expect(onEvent).toHaveBeenCalledTimes(1);
    expect(onEvent).toHaveBeenCalledWith({
      id: "evt-1",
      type: "message",
      data: { status: "running" },
    });
  });

  it("deduplicates events by lastEventId", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const onEvent = vi.fn();

    renderHook(() => useSSE("/api/events", onEvent));

    act(() => {
      MockEventSource.instances[0].onmessage?.({
        lastEventId: "evt-1",
        type: "message",
        data: '{"ok":true}',
      } as MessageEvent);
      MockEventSource.instances[0].onmessage?.({
        lastEventId: "evt-1",
        type: "message",
        data: '{"ok":true}',
      } as MessageEvent);
    });

    expect(onEvent).toHaveBeenCalledTimes(1);
  });

  it("allows duplicate events with different IDs", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const onEvent = vi.fn();

    renderHook(() => useSSE("/api/events", onEvent));

    act(() => {
      MockEventSource.instances[0].onmessage?.({
        lastEventId: "evt-1",
        type: "message",
        data: '{"ok":true}',
      } as MessageEvent);
      MockEventSource.instances[0].onmessage?.({
        lastEventId: "evt-2",
        type: "message",
        data: '{"ok":true}',
      } as MessageEvent);
    });

    expect(onEvent).toHaveBeenCalledTimes(2);
  });

  it("transitions to reconnecting after error and retries", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    vi.useFakeTimers();

    const { result } = renderHook(() =>
      useSSE("/api/events", vi.fn(), {
        reconnectIntervalMs: 1000,
        maxReconnectAttempts: 3,
      }),
    );

    act(() => {
      MockEventSource.instances[0].onopen?.();
    });
    expect(result.current.state).toBe("connected");

    act(() => {
      MockEventSource.instances[0].onerror?.();
    });

    expect(result.current.state).toBe("reconnecting");
    expect(result.current.retryCount).toBe(1);

    // Advance timer to trigger reconnect
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // A new EventSource should have been created
    expect(MockEventSource.instances.length).toBe(2);
  });

  it("exponential backoff increases delay with retries", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    vi.useFakeTimers();

    renderHook(() =>
      useSSE("/api/events", vi.fn(), {
        reconnectIntervalMs: 1000,
        maxReconnectAttempts: 5,
      }),
    );

    // First error (no onopen — connection fails immediately) — retry at 1000ms
    act(() => {
      MockEventSource.instances[0].onerror?.();
    });
    expect(MockEventSource.instances).toHaveLength(1);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(MockEventSource.instances).toHaveLength(2);

    // Second error without opening — retry at 2000ms (retryCount=2)
    act(() => {
      MockEventSource.instances[1].onerror?.();
    });

    // At 1999ms, third instance not yet created
    act(() => {
      vi.advanceTimersByTime(1999);
    });
    expect(MockEventSource.instances).toHaveLength(2);

    // At 2000ms total, third instance created
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(MockEventSource.instances).toHaveLength(3);
  });

  it("transitions to error state after max reconnect attempts", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    vi.useFakeTimers();
    const onFallback = vi.fn();

    const { result } = renderHook(() =>
      useSSE("/api/events", vi.fn(), {
        reconnectIntervalMs: 100,
        maxReconnectAttempts: 2,
        onFallback,
      }),
    );

    // Error 1 (no onopen — connection fails immediately)
    act(() => {
      MockEventSource.instances[0].onerror?.();
    });
    act(() => {
      vi.advanceTimersByTime(100);
    });

    // Error 2 — should hit max (retryCountRef is now 2)
    act(() => {
      MockEventSource.instances[1].onerror?.();
    });

    expect(result.current.state).toBe("error");
    expect(result.current.retryCount).toBe(2);
    expect(onFallback).toHaveBeenCalledTimes(1);
  });

  it("disconnect closes EventSource and sets disconnected state", () => {
    vi.stubGlobal("EventSource", MockEventSource);

    const { result } = renderHook(() => useSSE("/api/events", vi.fn()));

    act(() => {
      MockEventSource.instances[0].onopen?.();
    });

    expect(result.current.state).toBe("connected");

    act(() => {
      result.current.disconnect();
    });

    expect(result.current.state).toBe("disconnected");
    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
  });

  it("passes last_event_id in URL when provided", () => {
    vi.stubGlobal("EventSource", MockEventSource);

    renderHook(() =>
      useSSE("/api/events", vi.fn(), { lastEventId: "evt-42" }),
    );

    expect(MockEventSource.instances[0].url).toContain("last_event_id=evt-42");
  });

  it("cleans up EventSource on unmount", () => {
    vi.stubGlobal("EventSource", MockEventSource);

    const { unmount } = renderHook(() => useSSE("/api/events", vi.fn()));

    unmount();

    expect(MockEventSource.instances[0].close).toHaveBeenCalled();
  });

  it("allows events without lastEventId (no dedup for those)", () => {
    vi.stubGlobal("EventSource", MockEventSource);
    const onEvent = vi.fn();

    renderHook(() => useSSE("/api/events", onEvent));

    act(() => {
      MockEventSource.instances[0].onmessage?.({
        lastEventId: "",
        type: "message",
        data: '{"ok":true}',
      } as MessageEvent);
      MockEventSource.instances[0].onmessage?.({
        lastEventId: "",
        type: "message",
        data: '{"ok":true}',
      } as MessageEvent);
    });

    // Without IDs, no dedup happens
    expect(onEvent).toHaveBeenCalledTimes(2);
  });
});
