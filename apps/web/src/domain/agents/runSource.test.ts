// P-09-T05 (TASK-6211; SPEC-648 AC-8; P-09 T17's rules): the E6 core.
// "the RunStore polls at 1.5 s only while the run is active and the tab visible, orders by seq,
// resyncs on resync, and stops on a terminal state; ?static=1 freezes the scripted source."

import type { AgentRunOut, RunItemOut, RunItemsOut } from "@abacus/api-client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  PollingRunSource,
  RunStore,
  ScriptedRunSource,
  staticRequested,
  type Visibility,
} from "./runSource";

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

function page(
  seqs: number[],
  state: AgentRunOut["state"] = "running",
  resync = false,
): RunItemsOut {
  const last = Math.max(0, ...seqs);
  return { run: { ...RUN, state }, items: seqs.map(item), last_seq: last, resync, next_seq: last };
}

function visibility(hidden = false): Visibility & { set(v: boolean): void } {
  let isHidden = hidden;
  const listeners = new Set<() => void>();
  return {
    hidden: () => isHidden,
    onChange: (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    set(v: boolean) {
      isHidden = v;
      for (const l of listeners) l();
    },
  };
}

beforeEach(() => {
  vi.useFakeTimers();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("RunStore", () => {
  it("applies items once each, in seq order, and resync replaces them", () => {
    const store = new RunStore();
    store.apply(page([3, 1]));
    store.apply(page([2, 3]));
    expect(store.getSnapshot().items.map((i) => i.seq)).toEqual([1, 2, 3]);
    store.apply(page([7], "running", true));
    expect(store.getSnapshot().items.map((i) => i.seq)).toEqual([7]);
  });
});

describe("PollingRunSource", () => {
  it("polls every 1.5 s with the after_seq cursor and stops on a terminal state", async () => {
    const asked: number[] = [];
    const answers = [page([1, 2]), page([3]), page([4], "succeeded")];
    const source = new PollingRunSource(
      (after) => {
        asked.push(after);
        return Promise.resolve(answers.shift() ?? page([], "succeeded"));
      },
      { visibility: visibility() },
    );
    const store = new RunStore();
    store.connect(source);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(1500);
    await vi.advanceTimersByTimeAsync(1500);
    await vi.advanceTimersByTimeAsync(6000);
    expect(asked).toEqual([0, 2, 3]);
    expect(store.getSnapshot().items.map((i) => i.seq)).toEqual([1, 2, 3, 4]);
  });

  it("pauses while the tab is hidden and resumes when it is visible", async () => {
    const asked: number[] = [];
    const tab = visibility(true);
    const source = new PollingRunSource(
      (after) => {
        asked.push(after);
        return Promise.resolve(page([after + 1]));
      },
      { visibility: tab },
    );
    source.start();
    await vi.advanceTimersByTimeAsync(5000);
    expect(asked).toEqual([]);
    tab.set(false);
    await vi.advanceTimersByTimeAsync(0);
    expect(asked).toEqual([0]);
    source.stop();
  });
});

describe("ScriptedRunSource", () => {
  it("plays pages on its clock", async () => {
    const store = new RunStore();
    store.connect(
      new ScriptedRunSource([
        { page: page([1]), afterMs: 500 },
        { page: page([2]), afterMs: 500 },
      ]),
    );
    expect(store.getSnapshot().items).toEqual([]);
    await vi.advanceTimersByTimeAsync(500);
    expect(store.getSnapshot().items.map((i) => i.seq)).toEqual([1]);
    await vi.advanceTimersByTimeAsync(500);
    expect(store.getSnapshot().items.map((i) => i.seq)).toEqual([1, 2]);
  });

  it("?static=1 freezes on the final frame at once", () => {
    expect(staticRequested("?static=1")).toBe(true);
    const store = new RunStore();
    store.connect(
      new ScriptedRunSource(
        [
          { page: page([1]), afterMs: 500 },
          { page: page([2]), afterMs: 500 },
        ],
        { freeze: true },
      ),
    );
    expect(store.getSnapshot().items.map((i) => i.seq)).toEqual([1, 2]);
  });
});
