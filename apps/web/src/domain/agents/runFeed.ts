// The run feed hook (P-09 Story 1.3; P-09-T13 fixture-to-live swap): one `RunStore` per open run,
// fed by `PollingRunSource` on the live C6 route `GET /v1/agent-runs/{id}/items?after_seq=` with
// its cursor; it polls every 1.5 s while the run is active and the tab is visible and stops for
// good on a terminal state. P-10's SSE source plugs into the same store later.

import { agentRunItems } from "@abacus/api-client";
import { useEffect, useMemo } from "react";
import { PollingRunSource, RunStore, useRunStore } from "./runSource";
import type { RunFeed } from "./feedCore";

export { applyItems, EMPTY_FEED, isActive, POLL_MS, type RunFeed } from "./feedCore";

/** The live feed of one run. Polling stops when the run ends or the tab is hidden. */
export function useRunFeed(runId: string): RunFeed & { error: unknown } {
  const store = useMemo(() => new RunStore(), [runId]);
  useEffect(() => {
    const source = new PollingRunSource(async (afterSeq) => {
      const { data } = await agentRunItems({
        path: { run_id: runId },
        query: { after_seq: afterSeq },
        throwOnError: true,
      });
      return data;
    });
    return store.connect(source);
  }, [runId, store]);
  const feed = useRunStore(store);
  return { ...feed, error: store.getError() };
}
