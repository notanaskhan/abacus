// P-09-T13 (fixture-to-live swap): the run feed rides RunStore + PollingRunSource on the live
// items route with its cursor; run notifications deep-link to the run's trace.
import type { RunItemsOut } from "@abacus/api-client";
import { client } from "@abacus/api-client/client";
import { act, cleanup, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { installFixtureMode, json } from "../../app-core/fixture-mode";
import { feedHref, runTrace } from "../../shell/notifications";
import { useRunFeed } from "./runFeed";

beforeAll(() => {
  client.setConfig({ baseUrl: window.location.origin, throwOnError: true });
});

let restore: (() => void) | undefined;
afterEach(() => {
  cleanup();
  restore?.();
  restore = undefined;
});

const RUN = "00000000-0000-4000-8000-000000004118";

function page(afterSeq: number): RunItemsOut {
  const done = afterSeq >= 1;
  return {
    run: {
      id: RUN,
      agent: "engagement.agent",
      agent_label: "Engagement agent",
      state: done ? "succeeded" : "running",
      started_at: "2026-08-17T14:00:00Z",
      finished_at: done ? "2026-08-17T14:01:00Z" : null,
      duration_ms: done ? 60000 : null,
      initiator_name: "Marcus Delaney",
      subject: null,
    } as unknown as RunItemsOut["run"],
    items: done
      ? []
      : [
          {
            seq: 1,
            kind: "narration",
            code: "started",
            outcome: null,
            detail: null,
            actor: null,
            at: "2026-08-17T14:00:00Z",
          } as unknown as RunItemsOut["items"][number],
        ],
    last_seq: 1,
    resync: false,
  } as RunItemsOut;
}

describe("P-09-T13 live swap", () => {
  it("the feed polls the live items route with its after_seq cursor", async () => {
    const cursors: string[] = [];
    restore = installFixtureMode({
      state: "live",
      persona: "marcus-delaney",
      handlers: {
        "GET /v1/agent-runs/{run_id}/items": (r) => {
          const after = r.query.get("after_seq") ?? "0";
          cursors.push(after);
          return json(page(Number(after)));
        },
      },
    });
    const { result } = renderHook(() => useRunFeed(RUN));
    await waitFor(() => {
      expect(result.current.items).toHaveLength(1);
    });
    expect(cursors[0]).toBe("0");
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1600));
    });
    expect(cursors).toContain("1");
    expect(result.current.run?.state).toBe("succeeded");
  });

  it("a run's notification opens its trace over the engagement", () => {
    expect(runTrace("run_finished", "agent_run", RUN)).toBe(`?ov=run-trace:${RUN}`);
    expect(runTrace("run_needs_input", "agent_run", RUN)).toBe(`?ov=run-trace:${RUN}`);
    expect(runTrace("mention", "agent_run", RUN)).toBeNull();
    expect(runTrace("run_finished", "work_item", RUN)).toBeNull();
    const href = feedHref({
      id: "n1",
      kind: "run_finished",
      category: "run",
      created_at: "2026-08-17T14:01:00Z",
      engagement_id: "e1",
      facts: {},
      inline_actions: [],
      pending: false,
      read: false,
      subject: { id: RUN, type: "agent_run" },
      actor: { kind: "agent", display_name: "Engagement agent" },
    } as unknown as Parameters<typeof feedHref>[0]);
    expect(href?.to).toBe(`/engagements/e1?ov=run-trace:${RUN}`);
  });
});
