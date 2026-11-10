// The run feed hook (P-09 Story 1.3; P-09-T13 fixture-to-live swap; P-10-T35 SSE): one `RunStore`
// per open run, fed by `SseRunSource` behind `realtime.sse` (identifier-only events, each fetching
// its items through `GET /v1/agent-runs/{id}/items?after_seq=`), else `PollingRunSource` on the
// same route every 1.5 s while the run is active and the tab is visible. A dead stream falls back
// to 2 s polling from the same cursor. The dock, the trace drawer and the run pane read it here.

import { agentRunItems } from "@abacus/api-client";
import { useEffect, useMemo, useState } from "react";
import { useFlag } from "../../app-core/flags";
import type { RunFeed } from "./feedCore";
import { RunStore, useRunStore } from "./runSource";
import { runSourceFor } from "./sseRunSource";

export { applyItems, EMPTY_FEED, isActive, POLL_MS, type RunFeed } from "./feedCore";

/** The live feed of one run. Polling stops when the run ends or the tab is hidden. */
export function useRunFeed(runId: string): RunFeed & { error: unknown; announcement: string } {
  const store = useMemo(() => new RunStore(), [runId]);
  const sse = useFlag("realtime.sse") === true;
  const [announcement, setAnnouncement] = useState("");
  useEffect(() => {
    const source = runSourceFor(
      runId,
      async (afterSeq) => {
        const { data } = await agentRunItems({
          path: { run_id: runId },
          query: { after_seq: afterSeq },
          throwOnError: true,
        });
        return data;
      },
      {
        sse,
        onStateChange: (state) => {
          setAnnouncement(runStateWords(state));
        },
      },
    );
    return store.connect(source);
  }, [runId, store, sse]);
  const feed = useRunStore(store);
  return { ...feed, error: store.getError(), announcement };
}

const STATE_WORDS: Record<string, string> = {
  dispatched: "Dispatched",
  running: "Running",
  needs_input: "Waiting on your answer",
  blocked_on_decision: "Blocked on a decision",
  waiting_on_inputs: "Waiting on inputs",
  succeeded: "Finished",
  failed: "Failed",
  cancelled: "Stopped",
};

/** What a screen reader hears on a run-state change (and only then; items are never announced). */
export function runStateWords(state: string): string {
  return `Run ${(STATE_WORDS[state] ?? state.replaceAll("_", " ")).toLowerCase()}`;
}
