import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { usePermissions } from "./use-permissions";

vi.mock("@/components/auth-provider", () => ({
  useAuth: vi.fn(),
}));

import { useAuth } from "@/components/auth-provider";

function makeWrapper(permissions: string[], roles: string[] = []) {
  const mockUseAuth = vi.mocked(useAuth);
  mockUseAuth.mockReturnValue({
    user: {
      subject: "test-user",
      name: "Test",
      email: "test@test.com",
      organization_id: null,
      roles,
      team_ids: [],
      permissions,
    },
    loading: false,
    error: null,
    login: vi.fn(),
    logout: vi.fn(),
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <>{children}</>;
  };
}

describe("usePermissions", () => {
  it("can() returns true for exact permission match", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper(["portfolio:read", "portfolio:write"]),
    });

    expect(result.current.can("portfolio:read")).toBe(true);
    expect(result.current.can("portfolio:write")).toBe(true);
    expect(result.current.can("portfolio:delete")).toBe(false);
  });

  it("can() returns true for wildcard permission", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper(["*"]),
    });

    expect(result.current.can("anything:at_all")).toBe(true);
  });

  it("can() returns true for resource:* wildcard", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper(["portfolio:*"]),
    });

    expect(result.current.can("portfolio:read")).toBe(true);
    expect(result.current.can("portfolio:write")).toBe(true);
    expect(result.current.can("research:read")).toBe(false);
  });

  it("can() returns true for resource:admin", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper(["portfolio:admin"]),
    });

    expect(result.current.can("portfolio:read")).toBe(true);
    expect(result.current.can("portfolio:write")).toBe(true);
    expect(result.current.can("research:read")).toBe(false);
  });

  it("canAny() returns true if any permission matches", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper(["portfolio:read"]),
    });

    expect(result.current.canAny("portfolio:read", "portfolio:delete")).toBe(true);
    expect(result.current.canAny("research:read", "portfolio:delete")).toBe(false);
  });

  it("canAll() returns true only if all permissions match", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper(["portfolio:read", "research:read"]),
    });

    expect(result.current.canAll("portfolio:read", "research:read")).toBe(true);
    expect(result.current.canAll("portfolio:read", "portfolio:delete")).toBe(false);
  });

  it("isAdmin is true for * permission", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper(["*"]),
    });

    expect(result.current.isAdmin).toBe(true);
  });

  it("isAdmin is true for admin role", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper([], ["admin"]),
    });

    expect(result.current.isAdmin).toBe(true);
  });

  it("isAdmin is false for non-admin", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper(["portfolio:read"], ["analyst"]),
    });

    expect(result.current.isAdmin).toBe(false);
  });

  it("role returns first role", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper([], ["analyst", "viewer"]),
    });

    expect(result.current.role).toBe("analyst");
  });

  it("role returns null when no roles", () => {
    const { result } = renderHook(() => usePermissions(), {
      wrapper: makeWrapper([], []),
    });

    expect(result.current.role).toBeNull();
  });

  it("returns empty permissions when user is null", () => {
    vi.mocked(useAuth).mockReturnValue({
      user: null,
      loading: false,
      error: null,
      login: vi.fn(),
      logout: vi.fn(),
    });

    const { result } = renderHook(() => usePermissions(), {
      wrapper: ({ children }: { children: ReactNode }) => <>{children}</>,
    });

    expect(result.current.permissions).toEqual([]);
    expect(result.current.can("anything")).toBe(false);
  });
});
