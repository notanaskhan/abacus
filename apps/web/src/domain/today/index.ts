// The Today brief's reads and the rebuild (I-02-T16; docs/contracts/today.md), over the generated
// client only. Every count is the server's (I-COUNT); the panel formats and lays out.
import { todayBuildsMutation, todayOptions, todayQueryKey } from "@abacus/api-client/query";
import type { TodayVm } from "@abacus/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useRealtimeInterval } from "../../app-core/realtime-hooks";

/** `GET /v1/me/today`: the viewer's day (a building day is refetched on the record poll). */
export function useTodayBrief(enabled = true) {
  const interval = useRealtimeInterval("record");
  return useQuery({ ...todayOptions(), enabled, refetchInterval: interval, retry: false });
}

/** `POST /v1/me/today/builds`: Rebuild brief (three forced a day; 429 `rebuild_limit`). */
export function useRebuildBrief() {
  const queryClient = useQueryClient();
  const m = useMutation({
    ...todayBuildsMutation(),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: todayQueryKey() }),
  });
  return {
    ...m,
    rebuild: (briefDate: string, force: boolean | "background") =>
      m.mutateAsync({
        body: {
          brief_date: briefDate,
          mode: force === "background" ? "background" : force ? "force" : "missing",
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      }),
  };
}

/** I-02-T13 rest: a ready day whose briefs name gates closed since asks once for a background
 * rebuild of those engagements (the server debounces: 15 minutes, six a day). */
export function useStaleRebuild(vm: TodayVm | undefined): void {
  const rebuild = useRebuildBrief();
  const asked = useRef<string | null>(null);
  const stale = vm?.status === "ready" ? (vm.stale_engagements ?? []) : [];
  const key =
    stale.length === 0 || vm === undefined ? null : `${vm.brief_date}:${stale.join(",")}`;
  useEffect(() => {
    if (key === null || vm === undefined || asked.current === key) return;
    asked.current = key;
    rebuild.rebuild(vm.brief_date, "background").catch(() => undefined);
  }, [key, vm, rebuild]);
}

/** The guarded collapse preference (HOME-05 c): storage may be absent or refuse. */
const KEY = "accrued.today.collapsed";

export function readCollapsed(): boolean {
  try {
    return globalThis.localStorage.getItem(KEY) === "1";
  } catch {
    return false;
  }
}

export function writeCollapsed(collapsed: boolean): void {
  try {
    globalThis.localStorage.setItem(KEY, collapsed ? "1" : "0");
  } catch {
    // private mode or blocked storage: the preference lasts the page only
  }
}
