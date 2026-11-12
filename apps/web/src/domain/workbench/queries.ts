// Workbench sessions (W-02 §5.1; docs/contracts/workbench-sessions.md): WB-01's list, WB-02's
// picker and WB-03 d2's preview, over the generated client only. The server applies DEC-87's
// membership and walls before it answers: a walled session is absent from rows, counts and
// search, and nothing here counts what it cannot see (INV-3, DEC-43). `q` matches titles only.

import type { ContextOptionsOut, ListSessionsData } from "@abacus/api-client";
import {
  artifactPreviewOptions,
  contextOptionsOptions,
  getSessionOptions,
  listSessionsOptions,
} from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";
import { useRealtimeInterval } from "../../app-core/realtime-hooks";

export type SessionFilter = NonNullable<NonNullable<ListSessionsData["query"]>["filter"]>;
export type ContextTab = ContextOptionsOut["tab"];

/** WB-01's FilterButton menu, in order (C2 `workbench_session_filter`). */
export const SESSION_FILTERS: readonly SessionFilter[] = [
  "all",
  "mine",
  "via_agent",
  "running",
  "needs_answer",
];
export const CONTEXT_TABS: readonly ContextTab[] = ["client_record", "documents", "workpapers"];

export function isSessionFilter(v: unknown): v is SessionFilter {
  return typeof v === "string" && (SESSION_FILTERS as readonly string[]).includes(v);
}

export interface SessionListQuery {
  filter: SessionFilter;
  q: string;
}

function queryOf(f: SessionListQuery): NonNullable<ListSessionsData["query"]> {
  return { filter: f.filter, ...(f.q.trim() === "" ? {} : { q: f.q.trim() }) };
}

/** `GET /v1/workbench/sessions`: the rows and the filter counts. New sessions of teammates
 * reach the list on the 30-second list poll when the tab has no stream (W-02 §4.5). */
export function useWorkbenchSessions(f: SessionListQuery) {
  const interval = useRealtimeInterval("list");
  return useQuery({
    ...listSessionsOptions({ query: queryOf(f) }),
    refetchInterval: interval,
    retry: false,
  });
}

/** `GET /v1/workbench/sessions/{id}`: the thread (C6 v2). A locked session holds no item. */
export function useWorkbenchSession(sessionId: string | null) {
  const interval = useRealtimeInterval("record");
  return useQuery({
    ...getSessionOptions({ path: { session_id: sessionId ?? "" } }),
    enabled: sessionId !== null,
    refetchInterval: interval,
    retry: false,
  });
}

/** `GET /v1/workbench/context-options`: only records the viewer can open (AC-C3). */
export function useContextOptions(tab: ContextTab, q: string, sessionId: string | null) {
  return useQuery({
    ...contextOptionsOptions({
      query: {
        tab,
        ...(q.trim() === "" ? {} : { q: q.trim() }),
        ...(sessionId === null ? {} : { session_id: sessionId }),
      },
    }),
    retry: false,
  });
}

/** `GET /v1/run-artifacts/{id}/preview`: one sheet of the stored artifact (WB-03 d2). */
export function useArtifactPreview(artifactId: string | null, sheet: string | null) {
  return useQuery({
    ...artifactPreviewOptions({
      path: { artifact_id: artifactId ?? "" },
      ...(sheet === null ? {} : { query: { sheet } }),
    }),
    enabled: artifactId !== null,
    retry: false,
  });
}
