"use client";

import type { ReactNode } from "react";
import { usePermissions } from "@/hooks/use-permissions";

interface CanProps {
  permission: string;
  fallback?: ReactNode;
  children: ReactNode;
}

export function Can({ permission, fallback = null, children }: CanProps) {
  const { can } = usePermissions();
  return can(permission) ? <>{children}</> : <>{fallback}</>;
}

interface CanAnyProps {
  permissions: string[];
  fallback?: ReactNode;
  children: ReactNode;
}

export function CanAny({ permissions, fallback = null, children }: CanAnyProps) {
  const { canAny } = usePermissions();
  return canAny(...permissions) ? <>{children}</> : <>{fallback}</>;
}
