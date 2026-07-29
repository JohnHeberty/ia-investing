"use client";

import { useEffect, useRef, useCallback } from "react";
import { usePathname } from "next/navigation";
import { telemetry } from "@/lib/telemetry";

export function usePageView() {
  const pathname = usePathname();
  const prevPath = useRef(pathname);

  useEffect(() => {
    if (pathname !== prevPath.current) {
      telemetry.track("page_view", undefined, { from: prevPath.current });
      prevPath.current = pathname;
    }
  }, [pathname]);
}

export function useClickTracking(target: string, metadata?: Record<string, unknown>) {
  return useCallback(() => {
    telemetry.track("click", target, metadata);
  }, [target, metadata]);
}

export function useFormTracking(formName: string) {
  return {
    onSubmit: useCallback(() => {
      telemetry.track("form_submit", formName);
    }, [formName]),
    onError: useCallback((errors: Record<string, unknown>) => {
      telemetry.track("form_error", formName, { errors: Object.keys(errors) });
    }, [formName]),
  };
}
