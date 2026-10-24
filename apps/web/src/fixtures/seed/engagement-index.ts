// The ENG-01 slice of the Brightwater Hale seed (P-07-T27): the engagements index at E0, Mon Sep
// 14, 2026, 9:24 AM CT, as Margaret Okonkwo opens it. The 17 named rows are spec.md ROWS 1–17
// verbatim, in the screen's order (past due first, then by next deadline). The other 258
// engagements are not named in the handoff, so the slice carries only their counts, as the binders
// slice does (BND-01): segments 224 · 27 · 23 · 1 = 275 and tiles 1 + 4 + 0 + 128 + 0 + 140 + 2 =
// 275 (docs/screens/ENG-01.md, Figures). How the unnamed counts split by line and status is
// DEC-271: the audit line from the 27 audits of the seed (A1 to A27, audits.ts), every unnamed CAS
// engagement Active (a 2026 close engagement runs to December), and tax takes the rest. F-04-T31's
// exported seed replaces this file (`make fixtures`).
//
// Every body is typed against the generated client (`EngagementIndexRowOut`).

import type {
  EngagementIndexRowOut,
  EngagementLetterSummaryOut,
  EngagementStatus,
  EngagementWorkItemLineOut,
} from "@abacus/api-client";
import type { Seed } from "./index";
import { type OfficeName, SEATS, slugOf } from "./people";
import { entityIdOf, slugOfClient } from "./clients";
import { stableId } from "./prng";
import { officeIdOf } from "./shell";

export type ServiceLineCode = EngagementIndexRowOut["service_line"];
type Kind = EngagementWorkItemLineOut["kind"];

/** The seven tiles, in the screen's order (`declined` never shows). */
export const ENG01_TILES: readonly EngagementStatus[] = [
  "prospect",
  "accepted",
  "contracted",
  "active",
  "on_hold",
  "delivered",
  "archived",
];

/** §9 "275 engagements": the tiles at E0 (ENG-01a). */
export const ENG01_COUNTS: Readonly<Record<string, number>> = {
  prospect: 1,
  accepted: 4,
  contracted: 0,
  active: 128,
  on_hold: 0,
  delivered: 140,
  archived: 2,
};

/** The segments at E0: "All 275 · Tax 224 · Audit 27 · CAS 23 · Advisory 1". */
export const ENG01_SEGMENTS: Readonly<Record<ServiceLineCode, number>> = {
  tax: 224,
  audit: 27,
  cas: 23,
  advisory: 1,
};

interface Row {
  /** The id label: an audit's "A<n>", "feld", or a slug of the row. */
  ref: string;
  name: string;
  /** The client as the seed names it, and the entity when it is not the client itself. */
  client: string;
  entity?: string;
  type: EngagementIndexRowOut["type"];
  line: ServiceLineCode;
  period: string;
  start: string;
  end: string;
  office: OfficeName;
  partner: string;
  status: EngagementStatus;
  /** The work-item sub-line: how many items of which kind, the provider's line, its pill. */
  work?: { kind: Kind; n: number; label: string; pill?: [string, string] };
  letter: EngagementLetterSummaryOut;
  due?: { on: string; label?: string };
}

const signed = (on: string): EngagementLetterSummaryOut => ({
  status: "signed",
  signed_on: on,
  signed_count: 2,
  signer_count: 2,
});
const out = (
  event: "sent" | "viewed" | null,
  on: string | null,
  signedCount: number,
): EngagementLetterSummaryOut => ({
  status: "not_signed",
  last_event: event,
  last_event_on: on,
  signed_count: signedCount,
  signer_count: 2,
});
const NO_LETTER: EngagementLetterSummaryOut = { status: "not_signed" };
const CAL_2025 = ["2025-01-01", "2025-12-31"] as const;
const CAL_2026 = ["2026-01-01", "2026-12-31"] as const;
const FYE_JUN_2026 = ["2025-07-01", "2026-06-30"] as const;

/** spec.md ROWS 1–17, in the screen's order. */
export const ENG01_ROWS: readonly Row[] = [
  {
    ref: "copperleaf:2026-close",
    name: "2026 Close",
    client: "Copperleaf Coffee Roasters, Inc.",
    type: "cas_monthly_close",
    line: "cas",
    period: "Jan–Dec 2026",
    start: CAL_2026[0],
    end: CAL_2026[1],
    office: "Denver",
    partner: "PR",
    status: "active",
    work: { kind: "close", n: 12, label: "7 delivered · Aug in progress" },
    letter: signed("2026-03-03"),
    due: { on: "2026-09-10", label: "Aug close" },
  },
  {
    ref: "bluebird:2026-close",
    name: "2026 Close",
    client: "Bluebird Bakery Co.",
    type: "cas_monthly_close",
    line: "cas",
    period: "Jan–Dec 2026",
    start: CAL_2026[0],
    end: CAL_2026[1],
    office: "Chicago",
    partner: "PR",
    status: "active",
    work: { kind: "close", n: 12, label: "7 delivered · Aug in progress" },
    letter: signed("2026-01-09"),
    due: { on: "2026-09-12", label: "Aug close" },
  },
  {
    ref: "ridgeline:ty2025-1065",
    name: "TY2025 Form 1065",
    client: "Ridgeline Property Partners, LP",
    type: "tax_compliance",
    line: "tax",
    period: "TY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "New York",
    partner: "DR",
    status: "active",
    work: { kind: "tax_return", n: 1, label: "In review · Partner" },
    letter: signed("2026-02-06"),
    due: { on: "2026-09-15" },
  },
  {
    ref: "ridgeline:cost-segregation",
    name: "Cost segregation & §754 analysis",
    client: "Ridgeline Property Partners, LP",
    type: "advisory",
    line: "advisory",
    period: "Sep 2026–Feb 2027",
    start: "2026-09-01",
    end: "2027-02-28",
    office: "New York",
    partner: "DR",
    status: "accepted",
    work: { kind: "advisory_project", n: 1, label: "Scoping" },
    letter: out("sent", "2026-09-14", 0),
    due: { on: "2026-09-15", label: "§754 election deadline" },
  },
  {
    ref: "harborview:ty2025-1065",
    name: "TY2025 Form 1065",
    client: "Harborview Dental Properties, LP",
    type: "tax_compliance",
    line: "tax",
    period: "TY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "New York",
    partner: "DR",
    status: "active",
    work: { kind: "tax_return", n: 1, label: "Ready" },
    letter: signed("2026-02-09"),
    due: { on: "2026-09-15" },
  },
  {
    ref: "A2",
    name: "FY2026 FS Audit",
    client: "Granite Peak Outdoor Supply, Inc.",
    type: "fs_audit",
    line: "audit",
    period: "FYE 6/30/2026",
    start: FYE_JUN_2026[0],
    end: FYE_JUN_2026[1],
    office: "Denver",
    partner: "MO",
    status: "accepted",
    work: { kind: "assurance", n: 1, label: "Planning" },
    letter: out(null, null, 1),
    due: { on: "2026-09-16", label: "Letter due" },
  },
  {
    ref: "A7",
    name: "PY2025 EBP Audit",
    client: "Fairhaven Foods 401(k) Plan",
    type: "ebp_audit",
    line: "audit",
    period: "PY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "Chicago",
    partner: "MO",
    status: "accepted",
    work: { kind: "assurance", n: 1, label: "Planning" },
    letter: out("sent", "2026-09-08", 0),
    due: { on: "2026-09-18", label: "Letter due" },
  },
  {
    ref: "whitley:cp2000-ty2024",
    name: "CP2000 response · TY2024",
    client: "Marcus & Dana Whitley",
    type: "notice_response",
    line: "tax",
    period: "TY2024",
    start: "2024-01-01",
    end: "2024-12-31",
    office: "Denver",
    partner: "DR",
    status: "active",
    work: { kind: "notice", n: 1, label: "Analyzing" },
    letter: signed("2026-08-27"),
    due: { on: "2026-09-23", label: "Respond by" },
  },
  {
    ref: "bluestem:2026-close-from-oct",
    name: "2026 Close (from Oct)",
    client: "Bluestem Analytics, LLC",
    type: "cas_monthly_close",
    line: "cas",
    period: "Oct–Dec 2026",
    start: "2026-10-01",
    end: CAL_2026[1],
    office: "New York",
    partner: "PR",
    status: "accepted",
    letter: out("viewed", "2026-09-11", 0),
    due: { on: "2026-09-25", label: "Letter due" },
  },
  {
    ref: "calloway:ty2025-1041",
    name: "TY2025 Form 1041",
    client: "Calloway Family Trust",
    type: "tax_compliance",
    line: "tax",
    period: "TY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "Chicago",
    partner: "DR",
    status: "active",
    work: { kind: "tax_return", n: 1, label: "Prepared" },
    letter: signed("2026-02-04"),
    due: { on: "2026-09-30" },
  },
  {
    ref: "A1",
    name: "PY2025 EBP Audit",
    client: "Northwind Robotics, Inc.",
    entity: "Northwind Robotics 401(k) Plan",
    type: "ebp_audit",
    line: "audit",
    period: "PY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "Chicago",
    partner: "MO",
    status: "active",
    work: {
      kind: "assurance",
      n: 1,
      label: "Planning",
      pill: ["audit_engagement", "processing"],
    },
    letter: signed("2026-06-02"),
    due: { on: "2026-10-09", label: "Report target" },
  },
  {
    ref: "feld",
    name: "TY2025 Form 1040",
    client: "Jonah & Claire Feld",
    type: "tax_compliance",
    line: "tax",
    period: "TY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "New York",
    partner: "DR",
    status: "active",
    work: { kind: "tax_return", n: 1, label: "In review · Manager" },
    letter: signed("2026-02-02"),
    due: { on: "2026-10-15" },
  },
  {
    ref: "shah:ty2025-1040",
    name: "TY2025 Form 1040",
    client: "Meera Shah",
    type: "tax_compliance",
    line: "tax",
    period: "TY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "Chicago",
    partner: "NA",
    status: "active",
    work: { kind: "tax_return", n: 1, label: "Preparing" },
    letter: signed("2026-02-05"),
    due: { on: "2026-10-15" },
  },
  {
    ref: "thornbury:ty2025-1040",
    name: "TY2025 Form 1040",
    client: "Estate of Walter Thornbury",
    entity: "Walter Thornbury",
    type: "tax_compliance",
    line: "tax",
    period: "TY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "Chicago",
    partner: "NA",
    status: "active",
    work: { kind: "tax_return", n: 1, label: "Gathering" },
    letter: signed("2026-04-14"),
    due: { on: "2026-10-15" },
  },
  {
    ref: "A3",
    name: "FY2026 SSARS Review",
    client: "Lakeshore Literacy Alliance",
    type: "review",
    line: "audit",
    period: "FYE 6/30/2026",
    start: FYE_JUN_2026[0],
    end: FYE_JUN_2026[1],
    office: "Chicago",
    partner: "CM",
    status: "active",
    work: { kind: "assurance", n: 1, label: "Fieldwork" },
    letter: signed("2026-07-20"),
    due: { on: "2026-10-30", label: "Report target" },
  },
  {
    ref: "thornbury-estate:estate-returns",
    name: "Estate returns — final 1040 · 1041 · 706",
    client: "Estate of Walter Thornbury",
    type: "tax_compliance",
    line: "tax",
    period: "2026–2027",
    start: "2026-01-01",
    end: "2027-01-31",
    office: "Chicago",
    partner: "DR",
    status: "prospect",
    letter: NO_LETTER,
    due: { on: "2026-11-02", label: "Form 706" },
  },
  {
    ref: "A4",
    name: "FY2025 Preparation (AR-C 70)",
    client: "Juniper & Oak Interiors, LLC",
    type: "preparation",
    line: "audit",
    period: "FY2025",
    start: CAL_2025[0],
    end: CAL_2025[1],
    office: "Denver",
    partner: "PR",
    status: "archived",
    work: { kind: "assurance", n: 1, label: "Released Mar 2026" },
    letter: signed("2026-01-12"),
  },
];

/** The demo day (CT): the next-due tone and "n days" are counted from it. */
const TODAY = "2026-09-14";

function daysFrom(today: string, on: string): number {
  return Math.round(
    (Date.parse(`${on}T12:00:00Z`) - Date.parse(`${today}T12:00:00Z`)) / 86_400_000,
  );
}

function engagementIdOf(seed: Seed, ref: string): string {
  return seed.engagementIds[ref] ?? stableId(`engagement:${ref}`);
}

function partnerIdOf(initials: string): string | null {
  const seat = SEATS.find((s) => s.initials === initials);
  return seat === undefined ? null : stableId(`user:${slugOf(seat.name)}`);
}

/** A named row as `GET /v1/engagements/index` serves it. */
export function eng01Row(seed: Seed, row: Row): EngagementIndexRowOut {
  const client = seed.clients.find((c) => c.name === row.client);
  const slug = client?.slug ?? slugOfClient(row.client);
  const id = engagementIdOf(seed, row.ref);
  const work: EngagementWorkItemLineOut[] =
    row.work === undefined
      ? []
      : Array.from({ length: row.work.n }, (_, i) => ({
          id: stableId(`work-item:${row.ref}:${String(i)}`),
          kind: row.work?.kind ?? "close",
          label: row.work?.label ?? "",
          pill_object: i === 0 ? (row.work?.pill?.[0] ?? null) : null,
          pill_code: i === 0 ? (row.work?.pill?.[1] ?? null) : null,
        }));
  const days = row.due === undefined ? null : daysFrom(TODAY, row.due.on);
  return {
    id,
    name: row.name,
    client_id: seed.clientIds[slug] ?? stableId(`client:${slug}`),
    client_name: row.client,
    client_entity_id: entityIdOf(slug, row.entity ?? row.client),
    type: row.type,
    service_line: row.line,
    status: row.status,
    period_label: row.period,
    fiscal_period_start: row.start,
    fiscal_period_end: row.end,
    office_id: officeIdOf(row.office),
    office_name: row.office,
    partner_user_id: partnerIdOf(row.partner),
    partner_initials: row.partner,
    work_items: work,
    letter: row.letter,
    next_due:
      row.due === undefined || days === null
        ? null
        : {
            on: row.due.on,
            tone: days < 0 ? "past_due" : days <= 30 ? "soon" : "normal",
            label: row.due.label ?? null,
          },
    allowed_actions: [],
  };
}

/**
 * The unnamed engagements' counts by service line and status (DEC-271), so a segment recounts its
 * tiles: audit from the seed's 27 audits less the five named, CAS all Active, tax the rest.
 */
export function eng01Unnamed(seed: Seed): Record<ServiceLineCode, Record<string, number>> {
  const named = new Set(ENG01_ROWS.map((r) => engagementIdOf(seed, r.ref)));
  const audit: Record<string, number> = {};
  for (const e of seed.engagements) {
    if (e.service_line !== "audit" || named.has(e.id)) continue;
    audit[e.status] = (audit[e.status] ?? 0) + 1;
  }
  const namedIn = (line: ServiceLineCode, s?: EngagementStatus): number =>
    ENG01_ROWS.filter((r) => r.line === line && (s === undefined || r.status === s)).length;
  const cas = { active: ENG01_SEGMENTS.cas - namedIn("cas") };
  const tax: Record<string, number> = {};
  for (const s of ENG01_TILES) {
    const named = ENG01_ROWS.filter((r) => r.status === s).length;
    const rest =
      (ENG01_COUNTS[s] ?? 0) - named - (audit[s] ?? 0) - (s === "active" ? cas.active : 0);
    if (rest !== 0) tax[s] = rest;
  }
  return { audit, cas, tax, advisory: {} };
}
