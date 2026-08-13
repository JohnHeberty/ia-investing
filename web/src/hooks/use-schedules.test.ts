import { describe, expect, it } from "vitest";

import type { ScheduleRun } from "@/hooks/use-schedules";
import { selectTriggeredRun } from "@/hooks/use-schedules";

function run(startedAt: string, status = "running"): ScheduleRun {
  return {
    id: startedAt,
    schedule_id: "news-collection-issuer",
    workflow_id: `workflow-${startedAt}`,
    status,
    started_at: startedAt,
    finished_at: null,
    result_summary: null,
    error_message: null,
  };
}

describe("selectTriggeredRun", () => {
  it("finds a run started after the request even when the POST returns later", () => {
    const requestStartedAt = Date.parse("2026-08-13T12:00:00.000Z");
    const runs = [run("2026-08-13T12:00:00.050Z", "completed")];

    expect(selectTriggeredRun(runs, requestStartedAt)).toBe(runs[0]);
  });

  it("ignores runs that predate the trigger request", () => {
    const requestStartedAt = Date.parse("2026-08-13T12:00:00.000Z");
    const runs = [run("2026-08-13T11:59:59.999Z", "completed")];

    expect(selectTriggeredRun(runs, requestStartedAt)).toBeUndefined();
  });
});
