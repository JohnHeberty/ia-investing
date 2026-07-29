"use client";

import { useEffect } from "react";
import { telemetry } from "@/lib/telemetry";

export function TelemetryProvider({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    telemetry.startAutoFlush();

    const handleError = (event: ErrorEvent) => {
      telemetry.track("error", "window.onerror", {
        message: event.message,
        filename: event.filename,
        lineno: event.lineno,
      });
    };

    const handleRejection = (event: PromiseRejectionEvent) => {
      telemetry.track("error", "unhandledrejection", {
        reason: String(event.reason),
      });
    };

    window.addEventListener("error", handleError);
    window.addEventListener("unhandledrejection", handleRejection);

    return () => {
      window.removeEventListener("error", handleError);
      window.removeEventListener("unhandledrejection", handleRejection);
      telemetry.destroy();
    };
  }, []);

  return <>{children}</>;
}
