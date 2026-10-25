// The run feed (P-09 Story 1.3; docs/contracts/agent-runs.md §2): poll
// `GET /v1/agent-runs/{id}/items?after_seq=` every 1.5 s while the run is active and the tab is
// visible, apply each item once in seq order, and replace everything when the server says
// `resync`. SSE (P-10) can later feed the same reducer.

import type { AgentRunOut, RunItemOut, RunItemsOut } from "@abacus/api-client";
import { agentRunItems } from "@abacus/api-client";
import { useQuery } from "@tanstack/react-query";
import { useEffect, useReducer } from "react";

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

type Action = { kind: "page"; page: RunItemsOut } | { kind: "reset" };

function reduce(feed: RunFeed, action: Action): RunFeed {
  return action.kind === "reset" ? EMPTY_FEED : applyItems(feed, action.page);
}

/** The live feed of one run. Polling stops when the run ends or the tab is hidden. */
export function useRunFeed(runId: string): RunFeed & { error: unknown } {
  const [feed, dispatch] = useReducer(reduce, EMPTY_FEED);
  useEffect(() => {
    dispatch({ kind: "reset" });
  }, [runId]);
  const query = useQuery({
    queryKey: ["agentRunFeed", runId, feed.lastSeq],
    queryFn: async () =>
      (
        await agentRunItems({
          path: { run_id: runId },
          query: { after_seq: feed.lastSeq },
          throwOnError: true,
        })
      ).data,
    retry: false,
    refetchInterval: feed.run === null || isActive(feed.run) ? POLL_MS : false,
    refetchIntervalInBackground: false,
  });
  useEffect(() => {
    if (query.data !== undefined) dispatch({ kind: "page", page: query.data });
  }, [query.data]);
  return { ...feed, error: query.error };
}
