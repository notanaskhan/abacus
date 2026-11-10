// P-10-T35 (SPEC-647 AC-T1; DEC-3116): the caller's agent badge counts from
// `GET /v1/me/agent-events` (`{running, needs_answer, ready_for_review}`) behind `realtime.sse`;
// the shell polls its own counts when the flag is off or the stream dies.
import { client } from "@abacus/api-client/client";
import { useEffect, useState } from "react";
import { useFlag } from "../../app-core/flags";

export interface AgentBadge {
  running: number;
  needs_answer: number;
  ready_for_review: number;
}

export type BadgeOpener = (
  signal: AbortSignal,
  onBadge: (badge: AgentBadge) => void,
) => Promise<void>;

const defaultOpener: BadgeOpener = async (signal, onBadge) => {
  const { stream } = await client.sse.get<AgentBadge>({
    url: "/v1/me/agent-events",
    security: [{ scheme: "bearer", type: "http" }],
    signal,
    sseMaxRetryAttempts: 3,
    onSseEvent: (event) => {
      const data = event.data as Partial<AgentBadge> | undefined;
      if (data && typeof data.running === "number") {
        onBadge({
          running: data.running,
          needs_answer: data.needs_answer ?? 0,
          ready_for_review: data.ready_for_review ?? 0,
        });
      }
    },
  });
  // Counts arrive through onSseEvent; this drains the stream.
  const reader = stream[Symbol.asyncIterator]();
  while (!(await reader.next()).done) {
    // each count was handled by onSseEvent
  }
};

/** The badge counts while the stream lives; null when SSE is off or the stream ended. */
export function useAgentBadge(open: BadgeOpener = defaultOpener): AgentBadge | null {
  const sse = useFlag("realtime.sse") === true;
  const [badge, setBadge] = useState<AgentBadge | null>(null);
  useEffect(() => {
    if (!sse) {
      setBadge(null);
      return undefined;
    }
    const abort = new AbortController();
    void open(abort.signal, setBadge)
      .catch(() => undefined)
      .finally(() => {
        if (!abort.signal.aborted) setBadge(null); // dead stream: the shell's polling takes over
      });
    return () => {
      abort.abort();
    };
  }, [sse, open]);
  return badge;
}
