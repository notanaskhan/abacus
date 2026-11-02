// Notices (N-04 §5): NOT-01's reads over the generated client only. The filters are NOT-01's
// search params; the server applies them after `visible()` and walls, so a walled notice is absent
// from rows, tiles, the type counts and the summary line, and nothing here counts what it cannot
// see (INV-3, DEC-43). `q` is a list parameter and is never logged.

import type { NoticeRowOut, NoticesData } from "@abacus/api-client";
import { noticesOptions, noticesSummaryOptions } from "@abacus/api-client/query";
import { useQuery } from "@tanstack/react-query";

export type NoticeTile = NonNullable<NoticeRowOut["tile"]>;
export type NoticeAgency = NoticeRowOut["agency"];
/** NOT-01's Notice chip: the IRS codes the seed carries, and every state notice as one. */
export type NoticeTypeFilter = "cp2000" | "cp14" | "cp501" | "state";

export const NOTICE_TILES: readonly NoticeTile[] = [
  "new",
  "analyzing",
  "response_drafted",
  "awaiting",
];
export const NOTICE_AGENCIES: readonly NoticeAgency[] = ["irs", "state"];
export const NOTICE_TYPES: readonly NoticeTypeFilter[] = ["cp2000", "cp14", "cp501", "state"];

/** NOT-01's search params: `agency`, `type`, `assignee`, `respond_by` (7 or 30), `tile`, `q`. */
export interface NoticeFilters {
  agency: NoticeAgency | null;
  type: NoticeTypeFilter | null;
  assignee: string | null;
  respondBy: 7 | 30 | null;
  tile: NoticeTile | null;
  q: string;
}

export const DEFAULT_NOTICE_FILTERS: NoticeFilters = {
  agency: null,
  type: null,
  assignee: null,
  respondBy: null,
  tile: null,
  q: "",
};

export function isNoticeTile(v: unknown): v is NoticeTile {
  return typeof v === "string" && (NOTICE_TILES as readonly string[]).includes(v);
}

export function isNoticeAgency(v: unknown): v is NoticeAgency {
  return typeof v === "string" && (NOTICE_AGENCIES as readonly string[]).includes(v);
}

export function isNoticeType(v: unknown): v is NoticeTypeFilter {
  return typeof v === "string" && (NOTICE_TYPES as readonly string[]).includes(v);
}

export function isNarrowedNotices(f: NoticeFilters): boolean {
  return (
    f.agency !== null ||
    f.type !== null ||
    f.assignee !== null ||
    f.respondBy !== null ||
    f.tile !== null ||
    f.q.trim() !== ""
  );
}

function queryOf(f: NoticeFilters): NonNullable<NoticesData["query"]> {
  const query: NonNullable<NoticesData["query"]> = {};
  if (f.agency !== null) query.agency = f.agency;
  if (f.type !== null) query.type = f.type === "state" ? "state_generic" : f.type;
  if (f.assignee !== null) query.assignee = f.assignee;
  if (f.respondBy !== null) query.respond_by = f.respondBy;
  if (f.tile !== null) query.tile = f.tile;
  if (f.q.trim() !== "") query.q = f.q.trim();
  return query;
}

/** `GET /v1/notices`: rows by deadline risk, with the tiles' counts over the filters minus the
 * tile. */
export function useNotices(filters: NoticeFilters) {
  return useQuery({ ...noticesOptions({ query: queryOf(filters) }), retry: false });
}

/** `GET /v1/notices/summary`: the type tile, due within 7, blocked and the agent stage. */
export function useNoticesSummary() {
  return useQuery({ ...noticesSummaryOptions(), retry: false });
}
