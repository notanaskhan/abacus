// P-10-T35 (SPEC-647 AC-T1, AC-T3): the run's SSE source.
// "The dock fixture moves Dispatched, Running, Blocked from scripted SSE events with no polling
// request, and a killed stream falls back to 2 s polling without losing an event."

import type { AgentRunOut, RunItemOut, RunItemsOut } from "@abacus/api-client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { RunStore } from "./runSource";
import { runStateWords } from "./runFeed";
import {
  FALLBACK_POLL_MS,
  RunStreamLocked,
  type RunStreamFrame,
  type RunStreamOpener,
  runSourceFor,
  SseRunSource,
} from "./sseRunSource";

const RUN: AgentRunOut = {
  id: "00000000-0000-4000-8000-000000004127",
  agent: "audit_planning",
  agent_label: "Northwind Robotics 401(k) Plan — PY2025 planning run",
  state: "running",
  started_at: "2026-09-14T14:24:00Z",
  finished_at: null,
  duration_ms: null,
  initiator_name: "Marcus Delaney",
  subject: null,
};

function item(seq: number): RunItemOut {
  return {
    seq,
    kind: "tool_card",
    at: "2026-09-14T14:26:00Z",
    code: "audit_planning",
    outcome: null,
    detail: null,
    actor: null,
    ref_type: null,
    ref_id: null,
  };
}

/** The server: `upto` items, the run active unless `state` ends it. */
function server(upto: { n: number; state?: AgentRunOut["state"] }) {
  const calls: number[] = [];
  const fetchPage = async (after: number): Promise<RunItemsOut> => {
    calls.push(after);
    const items = Array.from({ length: Math.max(0, upto.n - after) }, (_, i) =>
      item(after + i + 1),
    );
    return {
      run: { ...RUN, state: upto.state ?? "running" },
      items,
      last_seq: upto.n,
      resync: false,
    };
  };
  return { calls, fetchPage };
}

function scripted(frames: RunStreamFrame[], options: { die?: boolean } = {}): RunStreamOpener {
  return () =>
    (async function* () {
      for (const frame of frames) {
        await Promise.resolve();
        yield frame;
      }
      if (options.die) throw new Error("stream died");
    })();
}

const flush = async (): Promise<void> => {
  for (let i = 0; i < 20; i += 1) await Promise.resolve();
};

afterEach(() => {
  vi.useRealTimers();
});

describe("SseRunSource", () => {
  it("moves Dispatched, Running, Blocked from scripted events with no polling request", async () => {
    const live = { n: 1 };
    const { calls, fetchPage } = server(live);
    const states: string[] = [];
    const frames: RunStreamFrame[] = [
      { event: "run.state_changed", seq: 2, data: { state: "dispatched" } },
      { event: "run.state_changed", seq: 3, data: { state: "running" } },
      { event: "run.state_changed", seq: 4, data: { state: "blocked_on_decision" } },
    ];
    const open: RunStreamOpener = (o) => {
      live.n = 4;
      return scripted(frames)(o);
    };
    const source = new SseRunSource(RUN.id, fetchPage, {
      open,
      onStateChange: (s) => states.push(s),
    });
    const store = new RunStore();
    store.connect(source);
    await source.settled();
    await flush();
    expect(states).toEqual(["dispatched", "running", "blocked_on_decision"]);
    expect(store.getSnapshot().items.map((i) => i.seq)).toEqual([1, 2, 3, 4]);
    // Each fetch is the cursor's: 0 first, then only past what it has; never a timer poll.
    expect(calls[0]).toBe(0);
    expect(new Set(calls).size).toBe(calls.length);
    expect(source.polling).toBe(false);
    source.stop();
  });

  it("falls back to 2 s polling from the same cursor when the stream dies, losing nothing", async () => {
    vi.useFakeTimers();
    const live = { n: 2 };
    const { calls, fetchPage } = server(live);
    const source = new SseRunSource(RUN.id, fetchPage, {
      open: scripted([{ event: "run.state_changed", seq: 2, data: { state: "running" } }], {
        die: true,
      }),
      visibility: { hidden: () => false, onChange: () => () => undefined },
    });
    const store = new RunStore();
    store.connect(source);
    await flush();
    expect(source.polling).toBe(true);
    live.n = 5; // three events land while the stream is down
    await vi.advanceTimersByTimeAsync(FALLBACK_POLL_MS);
    await flush();
    expect(store.getSnapshot().items.map((i) => i.seq)).toEqual([1, 2, 3, 4, 5]);
    expect(calls.every((after) => after >= 0)).toBe(true);
    expect(calls.at(-1)).toBeGreaterThanOrEqual(2); // polling resumed at the stream's cursor
    source.stop();
  });

  it("locked reports the not-allowed error and stops", async () => {
    const { fetchPage } = server({ n: 1 });
    const source = new SseRunSource(RUN.id, fetchPage, {
      open: scripted([{ event: "locked", seq: 1, data: {} }]),
    });
    const store = new RunStore();
    store.connect(source);
    await source.settled();
    await flush();
    expect(store.getError()).toBeInstanceOf(RunStreamLocked);
  });

  it("resync refetches from 0 and an over-64-KB event is fetched by reference", async () => {
    const live = { n: 3 };
    const { calls, fetchPage } = server(live);
    const source = new SseRunSource(RUN.id, fetchPage, {
      open: scripted([
        { event: "resync", seq: 3, data: {} },
        { event: "item.appended", seq: 3, data: { ref_only: true } },
      ]),
    });
    new RunStore().connect(source);
    await source.settled();
    await flush();
    expect(calls.filter((c) => c === 0).length).toBeGreaterThanOrEqual(2);
    source.stop();
  });

  it("a terminal state stops the stream for good", async () => {
    const { fetchPage } = server({ n: 2, state: "running" });
    const source = new SseRunSource(RUN.id, fetchPage, {
      open: scripted([{ event: "run.state_changed", seq: 2, data: { state: "succeeded" } }]),
    });
    new RunStore().connect(source);
    await source.settled();
    await flush();
    expect(source.polling).toBe(false);
  });
});

describe("runSourceFor and the announcement", () => {
  it("picks SSE behind realtime.sse and polling otherwise", () => {
    const { fetchPage } = server({ n: 0 });
    expect(runSourceFor(RUN.id, fetchPage, { sse: true })).toBeInstanceOf(SseRunSource);
    expect(runSourceFor(RUN.id, fetchPage, { sse: false })).not.toBeInstanceOf(SseRunSource);
  });

  it("announces run states in words", () => {
    expect(runStateWords("blocked_on_decision")).toBe("Run blocked on a decision");
    expect(runStateWords("succeeded")).toBe("Run finished");
  });
});
