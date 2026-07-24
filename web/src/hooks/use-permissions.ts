"use client";

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
  const perms = user?.permissions ?? [];

  return {
    permissions: perms,
    can: (permission) => hasPermission(perms, permission),
    canAny: (...permsList) => permsList.some((p) => hasPermission(perms, p)),
    canAll: (...permsList) => permsList.every((p) => hasPermission(perms, p)),
    isAdmin: perms.includes("*") || (user?.roles ?? []).includes("admin"),
    role: user?.roles?.[0] ?? null,
  };
}
