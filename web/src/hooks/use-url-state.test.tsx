import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

import { filterPresets, useUrlState } from "@/hooks/use-url-state";

// Mock next/navigation
const mockPush = vi.fn();
const mockPathname = "/test";
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  usePathname: () => mockPathname,
  useSearchParams: () => mockSearchParams,
}));

function Wrapper({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

beforeEach(() => {
  mockPush.mockClear();
});

describe("useUrlState", () => {
  it("returns default values when no URL params present", () => {
    mockSearchParams = new URLSearchParams();
    const defaults = { tab: "overview", sort: "name" };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [state] = result.current;
    expect(state.tab).toBe("overview");
    expect(state.sort).toBe("name");
  });

  it("reads values from URL params", () => {
    mockSearchParams = new URLSearchParams("tab=positions&sort=weight");
    const defaults = { tab: "overview" as string | undefined, sort: "name" as string | undefined };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [state] = result.current;
    expect(state.tab).toBe("positions");
    expect(state.sort).toBe("weight");
  });

  it("writes values to URL via router.push", () => {
    mockSearchParams = new URLSearchParams();
    const defaults = { tab: "overview" as string | undefined };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [, setState] = result.current;

    setState({ tab: "positions" });

    expect(mockPush).toHaveBeenCalledTimes(1);
    const callArg = mockPush.mock.calls[0][0] as string;
    expect(callArg).toContain("tab=positions");
  });

  it("removes param when value equals default", () => {
    mockSearchParams = new URLSearchParams("tab=positions");
    const defaults = { tab: "overview" as string | undefined };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [, setState] = result.current;

    setState({ tab: "overview" });

    expect(mockPush).toHaveBeenCalledTimes(1);
    const callArg = mockPush.mock.calls[0][0] as string;
    expect(callArg).not.toContain("tab=");
  });

  it("removes param when value is empty string", () => {
    mockSearchParams = new URLSearchParams("tab=positions");
    const defaults = { tab: "overview" as string | undefined };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [, setState] = result.current;

    setState({ tab: "" });

    expect(mockPush).toHaveBeenCalledTimes(1);
    const callArg = mockPush.mock.calls[0][0] as string;
    expect(callArg).not.toContain("tab=");
  });

  it("removes param when value is undefined", () => {
    mockSearchParams = new URLSearchParams("tab=positions");
    const defaults = { tab: "overview" as string | undefined };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [, setState] = result.current;

    setState({ tab: undefined });

    expect(mockPush).toHaveBeenCalledTimes(1);
    const callArg = mockPush.mock.calls[0][0] as string;
    expect(callArg).not.toContain("tab=");
  });

  it("pushes to pathname without query when all params removed", () => {
    mockSearchParams = new URLSearchParams("tab=positions");
    const defaults = { tab: "overview" as string | undefined };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [, setState] = result.current;

    setState({ tab: "overview" });

    expect(mockPush).toHaveBeenCalledTimes(1);
    const callArg = mockPush.mock.calls[0][0] as string;
    expect(callArg).toBe("/test");
  });

  it("handles array values with getAll", () => {
    mockSearchParams = new URLSearchParams("tag=a&tag=b");
    const defaults = { tag: [] as string[] };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [state] = result.current;
    expect(state.tag).toEqual(["a", "b"]);
  });

  it("writes array values with multiple append", () => {
    mockSearchParams = new URLSearchParams();
    const defaults = { tag: [] as string[] };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [, setState] = result.current;

    setState({ tag: ["x", "y"] });

    expect(mockPush).toHaveBeenCalledTimes(1);
    const callArg = mockPush.mock.calls[0][0] as string;
    expect(callArg).toContain("tag=x");
    expect(callArg).toContain("tag=y");
  });

  it("preserves existing params when updating one", () => {
    mockSearchParams = new URLSearchParams("existing=value");
    const defaults = { tab: "overview" as string | undefined };
    const { result } = renderHook(() => useUrlState(defaults), { wrapper: Wrapper });
    const [, setState] = result.current;

    setState({ tab: "positions" });

    expect(mockPush).toHaveBeenCalledTimes(1);
    const callArg = mockPush.mock.calls[0][0] as string;
    expect(callArg).toContain("existing=value");
    expect(callArg).toContain("tab=positions");
  });
});

describe("filterPresets", () => {
  it("has all required page presets", () => {
    expect(filterPresets).toHaveProperty("missionControl");
    expect(filterPresets).toHaveProperty("portfolio");
    expect(filterPresets).toHaveProperty("asset");
    expect(filterPresets).toHaveProperty("opportunities");
    expect(filterPresets).toHaveProperty("risk");
    expect(filterPresets).toHaveProperty("agents");
    expect(filterPresets).toHaveProperty("dataQuality");
  });

  it("asset preset has tab and evidenceFilter", () => {
    expect(filterPresets.asset.tab).toBe("metrics");
    expect(filterPresets.asset.evidenceFilter).toBe("all");
  });

  it("opportunities preset has stage, materiality, sortBy", () => {
    expect(filterPresets.opportunities.stage).toBeUndefined();
    expect(filterPresets.opportunities.materiality).toBeUndefined();
    expect(filterPresets.opportunities.sortBy).toBe("score");
  });

  it("risk preset has severity and type", () => {
    expect(filterPresets.risk.severity).toBeUndefined();
    expect(filterPresets.risk.type).toBeUndefined();
  });

  it("agents preset has status, capability, page", () => {
    expect(filterPresets.agents.status).toBeUndefined();
    expect(filterPresets.agents.capability).toBeUndefined();
    expect(filterPresets.agents.page).toBe("1");
  });

  it("missionControl preset has category, sortBy, status", () => {
    expect(filterPresets.missionControl.sortBy).toBe("confidence");
    expect(filterPresets.missionControl.category).toBeUndefined();
    expect(filterPresets.missionControl.status).toBeUndefined();
  });
});
