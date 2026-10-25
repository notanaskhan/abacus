// P-09 Story 1.3: items apply once, in seq order; resync replaces them.
import type { AgentRunOut, RunItemOut, RunItemsOut } from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { applyItems, EMPTY_FEED, isActive } from "./runFeed";

const RUN: AgentRunOut = {
  id: "r",
  agent: "engagement.agent",
  agent_label: "Engagement agent",
  state: "running",
  started_at: "2026-10-25T09:00:00Z",
  finished_at: null,
  duration_ms: null,
  initiator_name: "Dana Leader",
  subject: null,
};

function item(seq: number): RunItemOut {
  return {
    seq,
    kind: "narration",
    at: RUN.started_at,
    code: "agent.tick",
    outcome: "done",
    detail: null,
    actor: null,
    ref_type: null,
    ref_id: null,
  };
}

function page(seqs: number[], last: number, resync = false, run = RUN): RunItemsOut {
  return { run, items: seqs.map(item), last_seq: last, resync };
}

describe("run feed", () => {
  it("applies each item once, in seq order", () => {
    let feed = applyItems(EMPTY_FEED, page([2, 1], 2));
    feed = applyItems(feed, page([2, 3], 3));
    expect(feed.items.map((i) => i.seq)).toEqual([1, 2, 3]);
    expect(feed.lastSeq).toBe(3);
  });

  it("replaces everything on resync", () => {
    const feed = applyItems(applyItems(EMPTY_FEED, page([1, 2, 3], 3)), page([1], 1, true));
    expect(feed.items.map((i) => i.seq)).toEqual([1]);
    expect(feed.lastSeq).toBe(1);
  });

  it("stops polling once the run ends", () => {
    expect(isActive(RUN)).toBe(true);
    expect(isActive({ ...RUN, state: "succeeded" })).toBe(false);
    expect(isActive(null)).toBe(false);
  });
});
