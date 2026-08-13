"use client";

import { useCallback, useMemo } from "react";
import { useAuth } from "@/components/auth-provider";

export interface Permissions {
  permissions: string[];
  can: (permission: string) => boolean;
  canAny: (...perms: string[]) => boolean;
  canAll: (...perms: string[]) => boolean;
  isAdmin: boolean;
  role: string | null;
}

function hasPermission(permissions: string[], permission: string): boolean {
  if (permissions.includes("*")) return true;
  if (permissions.includes(permission)) return true;
  const resource = permission.includes(":") ? permission.split(":")[0] : permission;
  if (permissions.includes(`${resource}:*`)) return true;
  if (permissions.includes(`${resource}:admin`)) return true;
  return false;
}

export function usePermissions(): Permissions {
  const { user } = useAuth();
  const perms = useMemo(() => user?.permissions ?? [], [user?.permissions]);

  const can = useCallback((permission: string) => hasPermission(perms, permission), [perms]);
  const canAny = useCallback(
    (...permsList: string[]) => permsList.some((p) => hasPermission(perms, p)),
    [perms],
  );
  const canAll = useCallback(
    (...permsList: string[]) => permsList.every((p) => hasPermission(perms, p)),
    [perms],
  );
  const isAdmin = useMemo(
    () => perms.includes("*") || (user?.roles ?? []).includes("admin"),
    [perms, user?.roles],
  );
  const role = useMemo(() => user?.roles?.[0] ?? null, [user?.roles]);

  return { permissions: perms, can, canAny, canAll, isAdmin, role };
}
