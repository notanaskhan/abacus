// React glue for the real-time client (P-10-T30): start the tab's stream when `realtime.sse` is on,
// and give a query its `refetchInterval` (false while the stream is live; its poll otherwise).

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useSyncExternalStore } from "react";
import { useFlag } from "./flags";
import { type PollKind, POLL_MS, type RealtimeStatus, realtimeClient } from "./realtime";

/** The tab's stream status. */
export function useRealtimeStatus(): RealtimeStatus {
  const live = realtimeClient(useQueryClient());
  return useSyncExternalStore(
    (notify) => live.subscribe(notify),
    () => live.state,
    () => "off",
  );
}

/** Connect for `topics` while `realtime.sse` is on. One stream per tab carries the union of
 * every mounted surface's topics (TASK-7325), so a drawer adds to the page's and leaves it. */
export function useRealtimeStream(topics: readonly string[]): RealtimeStatus {
  const queryClient = useQueryClient();
  const enabled = useFlag("realtime.sse") === true;
  const key = topics.join(",");
  const owner = useRef(Symbol("realtime-surface"));
  useEffect(() => {
    const live = realtimeClient(queryClient);
    const me = owner.current;
    live.want(me, !enabled || key === "" ? [] : key.split(","));
    return () => {
      live.unwant(me);
    };
  }, [queryClient, enabled, key]);
  return useRealtimeStatus();
}

/** A query's `refetchInterval` for its surface kind (AC-T7). */
export function useRealtimeInterval(kind: PollKind): number | false {
  const status = useRealtimeStatus();
  return status === "live" || status === "connecting" ? false : POLL_MS[kind];
}
