// Notices v1 in fixture mode for NOT-01 (N-04-T05; docs/contracts/notices.md): the list and the
// summary on the stub's shapes (`ListPage[NoticeRowOut]`, `NoticesSummaryOut`), from seed/notices.ts,
// at E0 (Mon Sep 14, 2026). The tallies are the visible rows' (DEC-43): a tile's count is over the
// filters minus the tile, and the summary counts what the list would show unfiltered.

import type { ListPageNoticeRowOut, NoticeRowOut, NoticesSummaryOut } from "@abacus/api-client";
import { type FixtureHandler, json } from "../../app-core/fixture-mode";
import { SEATS } from "../seed/people";
import { NOTICES, type SeedNotice } from "../seed/notices";
import { stableId } from "../seed/prng";

/** The demo day the respond-by days count from (NOT-01 a: Mon Sep 14, 2026). */
export const NOTICES_DAY = "2026-09-14";
const DAY_MS = 86_400_000;

type Tile = NonNullable<NoticeRowOut["tile"]>;
const TILE_OF: Readonly<Record<SeedNotice["status"], Tile>> = {
  received: "new",
  analyzing: "analyzing",
  response_drafted: "response_drafted",
  awaiting_irs: "awaiting",
};
export const NOTICE_TILES: readonly Tile[] = ["new", "analyzing", "response_drafted", "awaiting"];

function days(on: string, from: string): number {
  return Math.round((Date.parse(`${on}T12:00:00Z`) - Date.parse(`${from}T12:00:00Z`)) / DAY_MS);
}

function riskOf(d: number | null): NoticeRowOut["risk"] {
  if (d === null) return "none";
  if (d <= 7) return "red";
  return d <= 30 ? "amber" : "none";
}

export function noticeId(key: string): string {
  return stableId(`notice:${key}`);
}

export function noticeRow(n: SeedNotice, today: string = NOTICES_DAY): NoticeRowOut {
  const d = n.respondBy === null ? null : days(n.respondBy, today);
  const seat = n.assignee === null ? undefined : SEATS.find((s) => s.initials === n.assignee);
  return {
    id: noticeId(n.key),
    engagement_id: stableId(`engagement:notice:${n.key}`),
    client_entity_id: stableId(`client-entity:${n.client}`),
    client_name: n.client,
    form_line: n.formLine,
    agency: n.agency,
    agency_name: n.agencyName,
    notice_type_key: n.typeKey,
    notice_code: n.code,
    title: n.title,
    tax_year: n.taxYear,
    received_on: n.receivedOn,
    respond_by: n.respondBy,
    respond_by_days: d,
    risk: riskOf(d),
    sent_on: n.sentOn,
    amounts: {
      tax: n.tax,
      interest: n.interest,
      penalty: null,
      total: n.total,
      interest_to: null,
    },
    position: n.position,
    status: n.status,
    tile: TILE_OF[n.status],
    assignee:
      seat === undefined
        ? null
        : { user_id: stableId(`user:${seat.initials}`), name: seat.name, initials: seat.initials },
    authorization: {
      kind: n.auth.kind,
      label: n.auth.label,
      on_file: n.auth.kind !== "none",
      can_represent: n.auth.kind === "form_2848",
      authorization_id: n.auth.kind === "none" ? null : stableId(`authorization:${n.key}`),
    },
    version: 1,
  };
}

/** Deadline risk: the soonest respond-by first; sent rows (no respond-by) after, newest sent first. */
function byRisk(a: NoticeRowOut, b: NoticeRowOut): number {
  if (a.respond_by !== null && b.respond_by !== null)
    return a.respond_by.localeCompare(b.respond_by);
  if (a.respond_by !== null) return -1;
  if (b.respond_by !== null) return 1;
  return (b.sent_on ?? "").localeCompare(a.sent_on ?? "");
}

export interface NoticeQuery {
  agency: string | null;
  type: string | null;
  assignee: string | null;
  respondBy: number | null;
  tile: string | null;
  q: string;
}

function typeBucket(row: NoticeRowOut): string {
  return row.agency === "state" ? "state" : row.notice_type_key;
}

function matches(row: NoticeRowOut, f: NoticeQuery, withTile: boolean): boolean {
  if (f.agency !== null && row.agency !== f.agency) return false;
  if (f.type !== null && typeBucket(row) !== f.type) return false;
  if (f.assignee !== null && row.assignee?.user_id !== f.assignee) return false;
  if (f.respondBy !== null && (row.respond_by_days === null || row.respond_by_days > f.respondBy))
    return false;
  if (withTile && f.tile !== null && row.tile !== f.tile) return false;
  const q = f.q.trim().toLowerCase();
  if (q !== "" && !`${row.client_name} ${row.notice_code} ${row.title}`.toLowerCase().includes(q))
    return false;
  return true;
}

export function queryOf(params: URLSearchParams): NoticeQuery {
  const respondBy = Number(params.get("respond_by"));
  return {
    agency: params.get("agency"),
    type: params.get("type") === "state_generic" ? "state" : params.get("type"),
    assignee: params.get("assignee"),
    respondBy: respondBy === 7 || respondBy === 30 ? respondBy : null,
    tile: params.get("tile"),
    q: params.get("q") ?? "",
  };
}

export function noticesPage(rows: readonly NoticeRowOut[], f: NoticeQuery): ListPageNoticeRowOut {
  const sorted = [...rows].sort(byRisk);
  const items = sorted.filter((r) => matches(r, f, true));
  const counts: Record<string, number> = Object.fromEntries(NOTICE_TILES.map((t) => [t, 0]));
  for (const r of sorted.filter((x) => matches(x, f, false))) {
    if (r.tile !== null) counts[r.tile] = (counts[r.tile] ?? 0) + 1;
  }
  const facet = (label: (r: NoticeRowOut) => [string, string] | null) => {
    const seen = new Map<string, { value: string; label: string; n: number }>();
    for (const r of sorted) {
      const pair = label(r);
      if (pair === null) continue;
      const hit = seen.get(pair[0]);
      if (hit === undefined) seen.set(pair[0], { value: pair[0], label: pair[1], n: 1 });
      else hit.n += 1;
    }
    return [...seen.values()];
  };
  return {
    items,
    next_cursor: null,
    total: items.length,
    counts,
    facets: {
      assignee: facet((r) => (r.assignee === null ? null : [r.assignee.user_id, r.assignee.name])),
    },
  };
}

export function noticesSummary(rows: readonly NoticeRowOut[]): NoticesSummaryOut {
  const tiles: Record<string, number> = Object.fromEntries(NOTICE_TILES.map((t) => [t, 0]));
  for (const r of rows) if (r.tile !== null) tiles[r.tile] = (tiles[r.tile] ?? 0) + 1;
  const n = (bucket: string) => rows.filter((r) => typeBucket(r) === bucket).length;
  return {
    tiles,
    by_type: [
      { key: "cp2000", label: "CP2000", count: n("cp2000") },
      { key: "cp14", label: "CP14", count: n("cp14") },
      { key: "cp501", label: "CP501", count: n("cp501") },
      { key: "state", label: "State", count: n("state") },
    ],
    open: rows.length,
    due_within_7: rows.filter((r) => r.respond_by_days !== null && r.respond_by_days <= 7).length,
    blocked: rows.filter((r) => !r.authorization.on_file).length,
    agent_stage: "live",
  };
}

/** NOT-01's reads over `rows` (the seed's nine by default; f: none). */
export function noticeHandlers(
  rows: readonly NoticeRowOut[] = NOTICES.map((n) => noticeRow(n)),
): Record<string, FixtureHandler> {
  return {
    "GET /v1/notices": ({ query }) => json(noticesPage(rows, queryOf(query))),
    "GET /v1/notices/summary": () => json(noticesSummary(rows)),
  };
}
