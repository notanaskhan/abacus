// Closes (C-01 §5; C-01-T33): CLS-01's reads over the generated client only. The filters are
// CLS-01's search params; the server applies them after `visible()` and walls, so a walled close
// is absent from rows, tiles and the summary line (SPEC-655 AC-4). `q` is a list parameter and is
// never logged.

import type { CloseRowOut, ListClosesData } from "@abacus/api-client";
import { listClosesOptions, runningClosesOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";

export type CloseStatus = CloseRowOut["status"];
/** The Status chip and tiles: the four tile statuses and "Past due" (CLS-01 c). */
export type CloseStatusFilter =
  "not_started" | "in_progress" | "in_review" | "delivered" | "past_due";

export const CLOSE_PERIODS = ["2026-06", "2026-07", "2026-08", "2026-09"] as const;
export type ClosePeriod = (typeof CLOSE_PERIODS)[number];
export const CLOSE_TILES = ["not_started", "in_progress", "in_review", "delivered"] as const;
export const CLOSE_STATUS_FILTERS: readonly CloseStatusFilter[] = [...CLOSE_TILES, "past_due"];

/** CLS-01's search params: `period`, `status`, `preparer`, `reviewer`, `attest`, `q`. */
export interface CloseFilters {
  period: ClosePeriod;
  status: CloseStatusFilter | null;
  preparer: string | null;
  reviewer: string | null;
  attest: boolean | null;
  q: string;
}

export const DEFAULT_CLOSE_FILTERS: CloseFilters = {
  period: "2026-08",
  status: null,
  preparer: null,
  reviewer: null,
  attest: null,
  q: "",
};

export function isClosePeriod(v: unknown): v is ClosePeriod {
  return typeof v === "string" && (CLOSE_PERIODS as readonly string[]).includes(v);
}

export function isCloseStatusFilter(v: unknown): v is CloseStatusFilter {
  return typeof v === "string" && (CLOSE_STATUS_FILTERS as readonly string[]).includes(v);
}

export function isNarrowedCloses(f: CloseFilters): boolean {
  return (
    f.status !== null ||
    f.preparer !== null ||
    f.reviewer !== null ||
    f.attest !== null ||
    f.q.trim() !== ""
  );
}

function queryOf(f: CloseFilters): ListClosesData["query"] {
  const query: ListClosesData["query"] = { period: f.period };
  if (f.status !== null) query.status = f.status;
  if (f.preparer !== null) query.preparer = f.preparer;
  if (f.reviewer !== null) query.reviewer = f.reviewer;
  if (f.attest !== null) query.attest = f.attest;
  if (f.q.trim() !== "") query.q = f.q.trim();
  return query;
}

/** `GET /v1/closes`: the period's rows with the four tiles and the summary line. */
export function useCloses(filters: CloseFilters) {
  return useQuery({ ...listClosesOptions({ query: queryOf(filters) }), retry: false });
}

/** `GET /v1/closes/running`: the running pill and its popover. */
export function useRunningCloses() {
  return useQuery({ ...runningClosesOptions(), retry: false });
}
