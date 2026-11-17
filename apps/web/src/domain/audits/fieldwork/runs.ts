// Fieldwork run rows, live (A-08-T24; DEC-5403): AUD-13 / AUD-26 Run and AUD-12 Begin. The rows
// are the API's (`GET /v1/analytics-sets/{id}/runs`): a code row reads "Code", an agent row
// "<initiator> via Agent". Each agent run's own progress is C6 v2's stream (`useRunFeed`); this
// read is the polling fallback, every 2 s while any run is still going. A firm whose data
// boundary is closed answers 409 `drafting_not_enabled` before any run exists: DF-04.

import type { RunRowOut, RunStateCountOut } from "@abacus/api-client";
import {
  analyticsRunRowsOptions,
  startAnalyticsRunsMutation,
  startRunMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { RunRow } from "./analytics";

export const RUN_POLL_MS = 2000;
type RunStateV2 = RunStateCountOut["state"];

// C6 v2's ended states (ADR-169): a run that succeeded, whose proposals were decided, or that was
// cancelled is done; `failed` is the one failure. Every other state is still going.
const DONE: ReadonlySet<RunStateV2> = new Set<RunStateV2>([
  "succeeded",
  "approved",
  "partially_approved",
  "rejected",
  "cancelled",
]);
const FAILED: ReadonlySet<RunStateV2> = new Set<RunStateV2>(["failed"]);

/** The kit's state for one API row: a code row is done; an agent row while any run is open. */
export function rowState(row: RunRowOut): RunRow["state"] {
  if (row.kind === "tie_out" || row.kind === "client_questions") return "done";
  if (row.states.some((s) => FAILED.has(s.state) && s.runs > 0)) return "failed";
  return row.states.every((s) => DONE.has(s.state)) ? "done" : "running";
}

export function toRunRows(rows: readonly RunRowOut[]): RunRow[] {
  return rows.map((r) => ({
    id: r.kind,
    label: r.label,
    meta: r.attribution,
    state: rowState(r),
  }));
}

/** DF-04: the firm's data boundary is closed (no run was recorded, no model was called). */
export function isDataBoundaryClosed(error: unknown): boolean {
  const detail = (error as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail === "drafting_not_enabled";
  const code = (detail as { code?: unknown } | null)?.code;
  return code === "drafting_not_enabled";
}

export function useAnalyticsRunRows(setId: string | null): {
  rows: RunRow[];
  loading: boolean;
} {
  const query = useQuery({
    ...analyticsRunRowsOptions({ path: { analytics_set_id: setId ?? "" } }),
    enabled: setId !== null,
    refetchInterval: (q) =>
      (q.state.data?.rows ?? []).some((r) => rowState(r) === "running") ? RUN_POLL_MS : false,
  });
  return { rows: toRunRows(query.data?.rows ?? []), loading: query.isPending && setId !== null };
}

export function useStartAnalyticsRuns(setId: string) {
  const queries = useQueryClient();
  return useMutation({
    ...startAnalyticsRunsMutation(),
    onSuccess: (data) => {
      queries.setQueryData(
        analyticsRunRowsOptions({ path: { analytics_set_id: setId } }).queryKey,
        data,
      );
    },
  });
}

export function useStartTestRun() {
  return useMutation(startRunMutation());
}
