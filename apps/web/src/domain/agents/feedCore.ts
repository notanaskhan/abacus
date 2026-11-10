// The run feed's pure core (P-09 Story 1.3; docs/contracts/agent-runs.md §2): poll
// `GET /v1/agent-runs/{id}/items?after_seq=` every 1.5 s while the run is active and the tab is
// visible, apply each item once in seq order, and replace everything when the server says
// `resync`. SSE (P-10) can later feed the same reducer. P-09-T13: split from runFeed.ts so the store and
// the polling source share it without an import cycle.

import type { AgentRunOut, RunItemOut, RunItemsOut } from "@abacus/api-client";

export const POLL_MS = 1500;
const ACTIVE: ReadonlySet<AgentRunOut["state"]> = new Set(["queued", "running"]);

export interface RunFeed {
  run: AgentRunOut | null;
  items: RunItemOut[];
  lastSeq: number;
}

export const EMPTY_FEED: RunFeed = { run: null, items: [], lastSeq: 0 };

export function isActive(run: AgentRunOut | null): boolean {
  return run !== null && ACTIVE.has(run.state);
}

/** Merge one response: new items once each, in seq order; `resync` replaces them all. */
export function applyItems(feed: RunFeed, page: RunItemsOut): RunFeed {
  if (page.resync) {
    const items = [...page.items].sort((a, b) => a.seq - b.seq);
    return { run: page.run, items, lastSeq: page.last_seq };
  }
  const seen = new Set(feed.items.map((i) => i.seq));
  const fresh = page.items.filter((i) => !seen.has(i.seq));
  const items = [...feed.items, ...fresh].sort((a, b) => a.seq - b.seq);
  return { run: page.run, items, lastSeq: Math.max(feed.lastSeq, page.last_seq) };
}
