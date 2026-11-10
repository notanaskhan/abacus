// React glue for the real-time client (P-10-T30): start the tab's stream when `realtime.sse` is on,
// and give a query its `refetchInterval` (false while the stream is live; its poll otherwise).

import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useSyncExternalStore } from "react";
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

/** Connect for `topics` while `realtime.sse` is on (one stream per tab; topics replace). */
export function useRealtimeStream(topics: readonly string[]): RealtimeStatus {
  const queryClient = useQueryClient();
  const enabled = useFlag("realtime.sse") === true;
  const key = topics.join(",");
  useEffect(() => {
    const live = realtimeClient(queryClient);
    if (!enabled || key === "") {
      live.stop();
      return undefined;
    }
    void live.start(key.split(","));
    return () => {
      live.stop();
    };
  }, [queryClient, enabled, key]);
  return useRealtimeStatus();
}

/** A query's `refetchInterval` for its surface kind (AC-T7). */
export function useRealtimeInterval(kind: PollKind): number | false {
  const status = useRealtimeStatus();
  return status === "live" || status === "connecting" ? false : POLL_MS[kind];
}
