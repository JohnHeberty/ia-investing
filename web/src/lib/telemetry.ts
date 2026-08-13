interface TelemetryEvent {
  event: string;
  target?: string;
  path: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

interface TelemetryConfig {
  flushInterval?: number;
  flushSize?: number;
  endpoint?: string;
  enabled?: boolean;
}

class Telemetry {
  private queue: TelemetryEvent[] = [];
  private flushTimer: ReturnType<typeof setInterval> | null = null;
  private config: Required<TelemetryConfig>;

  constructor(config: TelemetryConfig = {}) {
    this.config = {
      flushInterval: config.flushInterval ?? 30_000,
      flushSize: config.flushSize ?? 20,
      endpoint: config.endpoint ?? "/api/v1/events",
      enabled: config.enabled ?? true,
    };
  }

  track(event: string, target?: string, metadata?: Record<string, unknown>) {
    if (!this.config.enabled) return;
    this.queue.push({
      event,
      target,
      path: typeof window !== "undefined" ? window.location.pathname : "/",
      timestamp: Date.now(),
      metadata,
    });
    if (this.queue.length >= this.config.flushSize) {
      this.flush();
    }
  }

  async flush() {
    if (this.queue.length === 0 || typeof window === "undefined") return;
    const batch = this.queue.splice(0);
    try {
      await fetch(this.config.endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch }),
        keepalive: true,
      });
    } catch {
      batch.forEach((e) => {
        const retries = ((e.metadata?._retries as number) ?? 0) + 1;
        if (retries < 3) {
          this.queue.push({ ...e, metadata: { ...e.metadata, _retries: retries } });
        }
      });
    }
  }

  startAutoFlush() {
    if (this.flushTimer) return;
    this.flushTimer = setInterval(() => this.flush(), this.config.flushInterval);
    if (typeof document !== "undefined") {
      document.addEventListener("visibilitychange", this._onVisibilityChange);
    }
  }

  stopAutoFlush() {
    if (this.flushTimer) {
      clearInterval(this.flushTimer);
      this.flushTimer = null;
    }
    if (typeof document !== "undefined") {
      document.removeEventListener("visibilitychange", this._onVisibilityChange);
    }
  }

  private _onVisibilityChange = () => {
    if (document.visibilityState === "hidden") {
      this.flush();
    }
  };

  destroy() {
    this.stopAutoFlush();
    this.flush();
  }
}

export const telemetry = new Telemetry();
