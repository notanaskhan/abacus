// The Today brief's reads and the rebuild (I-02-T16; docs/contracts/today.md), over the generated
// client only. Every count is the server's (I-COUNT); the panel formats and lays out.
import {
  createTodoMutation,
  getSessionOptions,
  todayBuildsMutation,
  todayDrillOptions,
  todayHistoryBriefOptions,
  todayHistoryOptions,
  todayOptions,
  todayQueryKey,
  todayQuestionMutation,
} from "@abacus/api-client/query";
import type { AssignPrefill, SessionItemOut, TodayVm } from "@abacus/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
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

// --- I-02-T17 (DEC-4938): drill-in, assign, history and ask ------------------------------------

/** `GET /v1/me/today/work-items/{id}`: the drill-in (HOME-05 b, SHL-23 2). */
export function useTodayDrill(workItemId: string | null) {
  return useQuery({
    ...todayDrillOptions({ path: { work_item_id: workItemId ?? "" } }),
    enabled: workItemId !== null,
    retry: false,
  });
}

/** `GET /v1/me/today/history`: earlier briefs, newest first (90 days, Q3). */
export function useTodayHistory(enabled: boolean) {
  return useQuery({ ...todayHistoryOptions(), enabled, retry: false });
}

/** `GET /v1/me/today/history/{brief_id}`: one past brief, read only. */
export function usePastBrief(briefId: string | null) {
  return useQuery({
    ...todayHistoryBriefOptions({ path: { brief_id: briefId ?? "" } }),
    enabled: briefId !== null,
    retry: false,
  });
}

/** The SHL-17 prefill's anchor: `human_gate:<id>` as the to-do's anchor reference. */
export function anchorOf(ref: string): { anchor_kind: string; anchor_id: string } | null {
  const at = ref.indexOf(":");
  if (at <= 0) return null;
  return { anchor_kind: ref.slice(0, at), anchor_id: ref.slice(at + 1) };
}

/** Assign open items: one prefill at a time; the person presses Create (INV-1, INV-5). */
export function useAssignPrefills(prefills: readonly AssignPrefill[]) {
  const [index, setIndex] = useState<number | null>(null);
  const create = useMutation({ ...createTodoMutation() });
  const current = index !== null ? (prefills[index] ?? null) : null;
  const next = () => {
    setIndex((i) => (i === null || i + 1 >= prefills.length ? null : i + 1));
  };
  return {
    current,
    position: index,
    start: () => {
      setIndex(prefills.length > 0 ? 0 : null);
    },
    skip: next,
    cancel: () => {
      setIndex(null);
    },
    creating: create.isPending,
    /** Create (the person's): `POST /v1/todos` with the prefill's words, then the next one. */
    create: async (p: AssignPrefill) => {
      await create.mutateAsync({
        body: {
          title: p.title,
          assignee_user_id: p.assignee_user_id,
          due_on: p.due_on,
          scope_kind: "firm",
          anchor: anchorOf(p.anchor_ref),
        },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      next();
    },
  };
}

/** Ask about your day: `POST /v1/me/today/questions`, then the Today session's items (W-02). */
export function useAskToday(briefId: string | null | undefined) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const ask = useMutation({ ...todayQuestionMutation() });
  const interval = useRealtimeInterval("record");
  const session = useQuery({
    ...getSessionOptions({ path: { session_id: sessionId ?? "" } }),
    enabled: sessionId !== null,
    refetchInterval: interval,
    retry: false,
  });
  return {
    error: ask.error,
    pending,
    items: (session.data?.items ?? []) as readonly SessionItemOut[],
    send: async (text: string) => {
      if (!briefId) return;
      setPending(text);
      const accepted = await ask.mutateAsync({
        body: { text, brief_id: briefId },
        headers: { "Idempotency-Key": crypto.randomUUID() },
      });
      setSessionId(accepted.session_id);
      setPending(null);
    },
  };
}
