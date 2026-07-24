import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { Can, CanAny } from "./can";

vi.mock("@/hooks/use-permissions", () => ({
  usePermissions: vi.fn(),
}));

import { usePermissions } from "@/hooks/use-permissions";

describe("Can", () => {
  it("renders children when permission matches", () => {
    vi.mocked(usePermissions).mockReturnValue({
      can: () => true,
      canAny: () => true,
      canAll: () => true,
      isAdmin: false,
      permissions: [],
      role: null,
    });

    render(
      <Can permission="portfolio:read">
        <span>visible</span>
      </Can>,
    );

    expect(screen.getByText("visible")).toBeInTheDocument();
  });

  it("renders null when permission does not match", () => {
    vi.mocked(usePermissions).mockReturnValue({
      can: () => false,
      canAny: () => false,
      canAll: () => false,
      isAdmin: false,
      permissions: [],
      role: null,
    });

    const { container } = render(
      <Can permission="portfolio:delete">
        <span>should not appear</span>
      </Can>,
    );

    expect(container.textContent).toBe("");
  });

  it("renders fallback when permission does not match", () => {
    vi.mocked(usePermissions).mockReturnValue({
      can: () => false,
      canAny: () => false,
      canAll: () => false,
      isAdmin: false,
      permissions: [],
      role: null,
    });

    render(
      <Can permission="portfolio:delete" fallback={<span>no access</span>}>
        <span>should not appear</span>
      </Can>,
    );

    expect(screen.getByText("no access")).toBeInTheDocument();
  });
});

describe("CanAny", () => {
  it("renders children when any permission matches", () => {
    vi.mocked(usePermissions).mockReturnValue({
      can: () => false,
      canAny: (...perms: string[]) => perms.includes("portfolio:read"),
      canAll: () => false,
      isAdmin: false,
      permissions: [],
      role: null,
    });

    render(
      <CanAny permissions={["portfolio:read", "portfolio:delete"]}>
        <span>visible</span>
      </CanAny>,
    );

    expect(screen.getByText("visible")).toBeInTheDocument();
  });

  it("renders null when no permissions match", () => {
    vi.mocked(usePermissions).mockReturnValue({
      can: () => false,
      canAny: () => false,
      canAll: () => false,
      isAdmin: false,
      permissions: [],
      role: null,
    });

    const { container } = render(
      <CanAny permissions={["portfolio:delete", "research:write"]}>
        <span>should not appear</span>
      </CanAny>,
    );

    expect(container.textContent).toBe("");
  });
});
