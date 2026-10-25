// The audits index (A-01 §5.1, L3; docs/contracts/audits-cockpit.md §3): AUD-01's filters and
// `GET /v1/audits` over the generated client only. The server computes the tiles (`counts` per
// phase, minus the pressed tile), the segments (`facets.segment`), the type caption (`summary`) and
// the report-due tone over one `visible()` predicate; the screen adds nothing up.

import type { AuditEngagementStatus, AuditIndexRowOut, AuditsIndexData } from "@abacus/api-client";
import { auditsIndexInfiniteOptions } from "@abacus/api-client/query";
import { useInfiniteQuery } from "@tanstack/react-query";

export type AuditSegment = AuditIndexRowOut["segment"];
export type AuditType = AuditIndexRowOut["engagement_type"];
export type AuditQuery = NonNullable<AuditsIndexData["query"]>;
export type AuditDueWindow = "7d" | "14d" | "30d";

/** The R2 segments in the tabs bar's order (AUD-01 revision item 1). */
export const AUDIT_SEGMENTS: readonly AuditSegment[] = ["fs", "ebp", "review", "soc", "ia"];

/** The five tiles in the screen's order. DV-12: no Completion tile before DF-05. */
export const AUDIT_TILES = [
  "planning",
  "fieldwork",
  "in_review",
  "ready_to_release",
  "released",
] as const satisfies readonly AuditEngagementStatus[];
export type AuditTile = (typeof AUDIT_TILES)[number];

export const AUDIT_DUE_WINDOWS: readonly AuditDueWindow[] = ["7d", "14d", "30d"];

export interface AuditFilters {
  segment: AuditSegment | null;
  phase: AuditTile | null;
  type: AuditType | null;
  partner: string | null;
  office: string | null;
  due: AuditDueWindow | null;
  period: string | null;
  q: string;
}

export const DEFAULT_AUDIT_FILTERS: AuditFilters = {
  segment: null,
  phase: null,
  type: null,
  partner: null,
  office: null,
  due: null,
  period: null,
  q: "",
};

export function isAuditSegment(v: string | null | undefined): v is AuditSegment {
  return v != null && (AUDIT_SEGMENTS as readonly string[]).includes(v);
}

export function isAuditTile(v: string | null | undefined): v is AuditTile {
  return v != null && (AUDIT_TILES as readonly string[]).includes(v);
}

export function isAuditDue(v: string | null | undefined): v is AuditDueWindow {
  return v != null && (AUDIT_DUE_WINDOWS as readonly string[]).includes(v);
}

/** Anything but the default view (the segment is a view, not a filter). */
export function isNarrowedAudits(f: AuditFilters): boolean {
  return (
    f.phase !== null ||
    f.type !== null ||
    f.partner !== null ||
    f.office !== null ||
    f.due !== null ||
    f.period !== null ||
    f.q.trim() !== ""
  );
}

export function auditQueryOf(f: AuditFilters): AuditQuery {
  const q = f.q.trim();
  return {
    ...(f.segment === null ? {} : { segment: f.segment }),
    ...(f.phase === null ? {} : { phase: f.phase }),
    ...(f.type === null ? {} : { type: f.type }),
    ...(f.partner === null ? {} : { partner: f.partner }),
    ...(f.office === null ? {} : { office: f.office }),
    ...(f.due === null ? {} : { due: f.due }),
    ...(f.period === null ? {} : { period: f.period }),
    ...(q === "" ? {} : { q }),
  };
}

/** `GET /v1/audits`, keyset-paged ("Load more" appends the next page). */
export function useAuditIndex(filters: AuditFilters) {
  return useInfiniteQuery({
    ...auditsIndexInfiniteOptions({ query: auditQueryOf(filters) }),
    initialPageParam: {},
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    retry: false,
  });
}

const BASE_TYPE: Readonly<Record<AuditType, string>> = {
  fs_audit: "FS audit",
  ebp_audit: "EBP",
  review: "Review (AR-C 90)",
  compilation: "Compilation (AR-C 80)",
  preparation: "Preparation (AR-C 70)",
  agreed_upon_procedures: "Agreed-upon procedures",
  soc1: "SOC 1",
  soc2: "SOC 2",
  readiness: "Readiness",
  internal_audit: "Internal audit",
};

/** A type code in words, for the Type chip ("FS audit", "Review (AR-C 90)"). */
export function auditTypeWord(code: string): string {
  return (BASE_TYPE as Readonly<Record<string, string>>)[code] ?? code;
}

/** The Type column from the row's facts (AUD-01 spec ROWS): "EBP DC · §103(a)(3)(C)", "EBP
 * 403(b)", "FS audit", "FS audit (group)", "Review (AR-C 90)". The contract carries no report type
 * (Type 1 / Type 2) or internal-audit programme yet, so those rows read "SOC 2" and "Internal
 * audit" until X-01 and X-03 add them (DEC-340). */
export function auditTypeLabel(row: AuditIndexRowOut): string {
  if (row.ebp_plan_kind != null) {
    const kind = row.ebp_plan_kind === "403b" ? "403(b)" : row.ebp_plan_kind.toUpperCase();
    return `EBP ${kind}${row.limited_scope_103a3c === true ? " · §103(a)(3)(C)" : ""}`;
  }
  const base = BASE_TYPE[row.engagement_type];
  return row.is_group_audit === true ? `${base} (group)` : base;
}

/** AUD-01's URL params (A-01 §5.1): `?segment=&phase=&type=&partner=&office=&due=&period=&q=`. */
export type AuditSearch = Partial<Record<keyof AuditFilters, string>>;

const SEARCH_KEYS = [
  "segment",
  "phase",
  "type",
  "partner",
  "office",
  "due",
  "period",
  "q",
] as const satisfies readonly (keyof AuditFilters)[];

/** The URL's params as filters; an unknown value is the default (`segment=all`, `due=any`). */
export function auditFiltersOf(search: Readonly<Record<string, unknown>>): AuditFilters {
  const str = (key: string): string | null => {
    const v = search[key];
    return typeof v === "string" && v !== "" ? v : null;
  };
  const segment = str("segment");
  const phase = str("phase");
  const due = str("due");
  return {
    segment: isAuditSegment(segment) ? segment : null,
    phase: isAuditTile(phase) ? phase : null,
    type: (str("type") as AuditType | null) ?? null,
    partner: str("partner"),
    office: str("office"),
    due: isAuditDue(due) ? due : null,
    period: str("period"),
    q: str("q") ?? "",
  };
}

/** Filters as URL params, defaults left out. */
export function auditSearchOf(f: AuditFilters): AuditSearch {
  const out: AuditSearch = {};
  for (const key of SEARCH_KEYS) {
    const v = f[key];
    if (typeof v === "string" && v.trim() !== "") out[key] = v;
  }
  return out;
}

export const AUDIT_SEARCH_KEYS = SEARCH_KEYS;
