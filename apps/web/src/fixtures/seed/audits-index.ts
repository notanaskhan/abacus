// A-01-T03: the audits family fixtures (docs/contracts/audits-cockpit.md), typed with the generated
// client. AUD-01's 27 rows are the E0 audit-core engagements (seed/audits.ts) with the index facts
// verbatim from the AUD-01 spec's ROWS (EP / Mgr, office, PBC, report due, tags, archive) and the
// Source Documents aggregate is Northwind's 24 requests (seed/requests.ts) by category.
// `auditIndexPage` is the envelope a fixture handler answers: filters, tiles as `counts` per phase
// minus the active tile (P-36), segments as facets and the type caption, from one predicate.
// Brightwater Hale, synthetic. Fixture scenarios register every tag provider, so frames keep their
// designed tags (A-01 DV-10: live tags only from registered providers).

import type {
  AuditEngagementStatus,
  AuditIndexPage,
  AuditIndexRowOut,
  AuditIndexSummaryOut,
  EngagementOut,
  Facet,
  RequestItemOut,
  SourceDocumentGroupOut,
  SourceDocumentRowOut,
  SourceDocumentsOut,
  WorkItemOut,
} from "@abacus/api-client";
import { stableId } from "./prng";
import { SEATS, slugOf } from "./people";

type Segment = AuditIndexRowOut["segment"];
type DueWindow = "any" | "7d" | "14d" | "30d";

/** AUD-01 tile order (spec: group rows in tile order). DV-12: no Completion tile before DF-05. */
export const TILE_PHASES: readonly AuditEngagementStatus[] = [
  "planning",
  "fieldwork",
  "in_review",
  "ready_to_release",
  "released",
];

interface IndexFacts {
  epMgr: string;
  office: "Chicago" | "Denver" | "New York";
  /** "11 of 24"; null before G3 (Fairhaven, DEC-39). */
  pbc: readonly [number, number] | null;
  due: string | null;
  period: string;
  plan?: "dc" | "403b";
  limited?: true;
  tags?: readonly (readonly [source: string, code: string, text: string, metadata: boolean])[];
  released?: string;
  archive?: { state: "archiving" | "archived"; ref?: string };
  run?: true;
}

const PY = "PY2025";
const FYE_JUN = "FYE 6/30/2026";

// Keyed by the engagement's entity name, verbatim from the AUD-01 spec ROWS.
const FACTS: Readonly<Record<string, IndexFacts>> = {
  "Northwind Robotics 401(k) Plan": {
    epMgr: "MO / HL",
    office: "Chicago",
    pbc: [11, 24],
    due: "2026-10-09",
    period: PY,
    plan: "dc",
    limited: true,
    run: true,
  },
  "Fairhaven Foods 401(k) Plan": {
    epMgr: "MO / LK",
    office: "Chicago",
    pbc: null,
    due: "2026-10-09",
    period: PY,
    plan: "dc",
    tags: [["letter_sent", "letter_sent", "Letter sent Sep 8", true]],
  },
  "Tamarack Health System 403(b) Plan": {
    epMgr: "CM / OH",
    office: "New York",
    pbc: [6, 26],
    due: "2026-10-13",
    period: PY,
    plan: "403b",
  },
  "Granite Peak Outdoor Supply, Inc.": {
    epMgr: "MO / HL",
    office: "Denver",
    pbc: [9, 41],
    due: "2026-10-28",
    period: FYE_JUN,
    tags: [["materiality", "materiality_pending", "Materiality decision pending", false]],
  },
  "Larimer Cooperative Grocery": {
    epMgr: "TW / LK",
    office: "Denver",
    pbc: [4, 38],
    due: "2026-10-28",
    period: FYE_JUN,
  },
  "Halcyon Foods Distribution, Inc.": {
    epMgr: "TW / OH",
    office: "Chicago",
    pbc: [7, 44],
    due: "2026-10-28",
    period: FYE_JUN,
  },
  "Riverbend Community Theater": {
    epMgr: "CM / OH",
    office: "New York",
    pbc: [3, 14],
    due: "2026-11-13",
    period: FYE_JUN,
  },
  "Sterling Freight 401(k) Plan": {
    epMgr: "TW / LK",
    office: "Chicago",
    pbc: [22, 24],
    due: "2026-10-09",
    period: PY,
    plan: "dc",
  },
  "Westbrook Engineering 401(k) Plan": {
    epMgr: "CM / OH",
    office: "New York",
    pbc: [19, 22],
    due: "2026-10-09",
    period: PY,
    plan: "dc",
  },
  "Arbor Senior Living 401(k) Plan": {
    epMgr: "MO / HL",
    office: "Chicago",
    pbc: [20, 24],
    due: "2026-10-09",
    period: PY,
    plan: "dc",
  },
  "Clearwater Credit Union 401(k) Plan": {
    epMgr: "MO / LK",
    office: "Denver",
    pbc: [23, 24],
    due: "2026-10-09",
    period: PY,
    plan: "dc",
  },
  "Granite Peak Outdoor Supply 401(k) Plan": {
    epMgr: "MO / HL",
    office: "Denver",
    pbc: [18, 24],
    due: "2026-10-09",
    period: PY,
    plan: "dc",
  },
  "Sable Creek Homeowners Association": {
    epMgr: "CM / OH",
    office: "Denver",
    pbc: [30, 36],
    due: "2026-10-28",
    period: FYE_JUN,
  },
  "Lakeshore Literacy Alliance": {
    epMgr: "CM / LK",
    office: "Chicago",
    pbc: [12, 15],
    due: "2026-11-13",
    period: FYE_JUN,
  },
  "Hillcrest Montessori School": {
    epMgr: "TW / OH",
    office: "Chicago",
    pbc: [11, 14],
    due: "2026-11-13",
    period: FYE_JUN,
  },
  "Fenwick Family Foundation": {
    epMgr: "PR / HV",
    office: "Denver",
    pbc: [8, 9],
    due: "2026-09-30",
    period: "FY2025",
  },
  "Keel & Compass Marine 401(k) Plan": {
    epMgr: "TW / LK",
    office: "Chicago",
    pbc: [24, 24],
    due: "2026-10-02",
    period: PY,
    plan: "dc",
  },
  "Redtail Construction 401(k) Plan": {
    epMgr: "CM / OH",
    office: "New York",
    pbc: [22, 22],
    due: "2026-10-02",
    period: PY,
    plan: "dc",
  },
  "Hearthstone Hospitality 401(k) Plan": {
    epMgr: "TW / HL",
    office: "Chicago",
    pbc: [24, 24],
    due: "2026-10-05",
    period: PY,
    plan: "dc",
  },
  "Oakline Software, Inc.": {
    epMgr: "CM / OH",
    office: "New York",
    pbc: [40, 40],
    due: "2026-09-28",
    period: "FYE 3/31/2026",
    tags: [["eqr", "eqr", "EQR · TW", true]],
  },
  "Wildflower Land Trust": {
    epMgr: "CM / LK",
    office: "Denver",
    pbc: [14, 14],
    due: "2026-10-16",
    period: FYE_JUN,
  },
  "Kettle & Kiln Pottery, LLC": {
    epMgr: "PR / HV",
    office: "Denver",
    pbc: [6, 6],
    due: "2026-09-25",
    period: "FY2025",
  },
  "Cobalt Ridge Manufacturing 401(k) Plan": {
    epMgr: "TW / LK",
    office: "Chicago",
    pbc: [24, 24],
    due: "2026-09-18",
    period: PY,
    plan: "dc",
    tags: [["rep_letter", "rep_letter_sent", "Rep letter sent", false]],
  },
  "Halden Health 403(b) Plan": {
    epMgr: "CM / OH",
    office: "New York",
    pbc: [26, 26],
    due: "2026-09-21",
    period: PY,
    plan: "403b",
    tags: [["rep_letter", "rep_letter_viewed", "Rep letter viewed", false]],
  },
  "Bayside Electric Cooperative 401(k) Plan": {
    epMgr: "CM / OH",
    office: "New York",
    pbc: [24, 24],
    due: null,
    period: PY,
    plan: "dc",
    released: "2026-07-29",
    archive: { state: "archiving" },
  },
  "Meridian Tool & Die, Inc.": {
    epMgr: "MO / HL",
    office: "Chicago",
    pbc: [39, 39],
    due: null,
    period: "FYE 12/31/2025",
    released: "2026-04-17",
    archive: { state: "archived", ref: "CaseWare BH-2025-031" },
  },
  "Juniper & Oak Interiors, LLC": {
    epMgr: "PR / HV",
    office: "Denver",
    pbc: [5, 5],
    due: null,
    period: "FY2025",
    released: "2026-03-20",
    tags: [["no_report", "no_report", "No report", true]],
    archive: { state: "archived" },
  },
};

const ARCHIVE_DAYS = 60; // G9: archive within 60 days of release (blueprint §3.3.2)
const DAY_MS = 86_400_000;

function days(fromIso: string, toIso: string): number {
  return Math.round((Date.parse(toIso) - Date.parse(fromIso)) / DAY_MS);
}

function addDays(iso: string, n: number): string {
  return new Date(Date.parse(iso) + n * DAY_MS).toISOString().slice(0, 10);
}

function segmentOf(type: EngagementOut["type"], plan: IndexFacts["plan"]): Segment {
  if (type === "ebp_audit" || plan !== undefined) return "ebp";
  if (type === "fs_audit") return "fs";
  if (type === "soc1" || type === "soc2") return "soc";
  if (type === "internal_audit") return "ia";
  return "review";
}

function tone(
  due: string | null,
  today: string,
): NonNullable<AuditIndexRowOut["report_due_tone"]> | null {
  if (due === null) return null;
  const left = days(today, due);
  if (left < 0) return "past_due";
  // Sep 21 is seven days from Sep 14 and the spec draws it amber: red means under a week (DEC-263).
  if (left < 7) return "within_7_days";
  if (left <= 30) return "within_30_days";
  return "later";
}

const officeIdOf = (name: string) => stableId(`office:${name}`);

/** AUD-01's 27 rows at `today` (the demo clock's date), from the seed's engagements. */
export function auditIndexRows(
  engagements: readonly EngagementOut[],
  workItems: Readonly<Record<string, WorkItemOut[]>>,
  today: string,
): AuditIndexRowOut[] {
  const rows: AuditIndexRowOut[] = [];
  for (const e of engagements) {
    const facts = FACTS[e.client_entity_name];
    const item = (workItems[e.id] ?? []).find((w) => w.kind === "assurance");
    if (facts === undefined || item === undefined) continue;
    const [partner, manager] = facts.epMgr.split(" / ");
    const marcus = SEATS.find((s) => s.initials === "MD");
    const releasedArchive =
      facts.archive?.state === "archiving" && facts.released !== undefined
        ? days(today, addDays(facts.released, ARCHIVE_DAYS))
        : null;
    rows.push({
      work_item_id: item.id,
      engagement_id: e.id,
      client_id: e.client_id,
      client_name: e.client_name,
      name: e.client_entity_name,
      engagement_type: e.type as AuditIndexRowOut["engagement_type"],
      segment: segmentOf(e.type, facts.plan),
      ebp_plan_kind: facts.plan ?? null,
      limited_scope_103a3c: facts.limited === true,
      is_group_audit: false,
      period_label: facts.period,
      phase: (item.phase ?? "planning") as AuditEngagementStatus,
      released_on: facts.released ?? null,
      run_badge:
        facts.run === true && marcus !== undefined
          ? {
              run_id: stableId("run:4127"),
              run_number: 1,
              started_at: "2026-09-14T14:24:00.000Z", // 9:24 AM CT
              started_by_user_id: stableId(`user:${slugOf(marcus.name)}`),
              started_by_name: marcus.name,
              workpapers_complete: 1,
              workpapers_total: 14,
              blocked_on_role: "partner",
            }
          : null,
      tags: (facts.tags ?? []).map(([source, code, text, metadata]) => ({
        source,
        code,
        text,
        classification: metadata ? "metadata" : "content",
      })),
      pbc: facts.pbc === null ? null : { received: facts.pbc[0], total: facts.pbc[1] },
      partner_initials: partner ?? null,
      manager_initials: manager ?? null,
      office_id: officeIdOf(facts.office),
      office_name: facts.office,
      report_due_on: facts.due,
      report_due_tone: tone(facts.due, today),
      archive:
        facts.archive === undefined
          ? null
          : {
              state: facts.archive.state,
              days_left: releasedArchive,
              firm_tool_ref: facts.archive.ref ?? null,
            },
      allowed_actions: [],
    });
  }
  const tileOrder = (p: AuditEngagementStatus) => TILE_PHASES.indexOf(p);
  return rows.sort(
    (a, b) =>
      tileOrder(a.phase) - tileOrder(b.phase) ||
      (a.report_due_on ?? "9999").localeCompare(b.report_due_on ?? "9999") ||
      a.name.localeCompare(b.name),
  );
}

export interface AuditIndexQuery {
  segment?: Segment | undefined;
  phase?: AuditEngagementStatus;
  type?: AuditIndexRowOut["engagement_type"];
  office?: string;
  due?: DueWindow;
  q?: string;
}

/** The segments a firm sees: SOC & IT and Internal audit only under their entitlements (P-28);
 * Brightwater Hale holds neither at E0, both in the wave-7 view (AUD-01 g, h). */
export const E0_SEGMENTS: readonly Segment[] = ["fs", "ebp", "review"];
export const E2_SEGMENTS: readonly Segment[] = ["fs", "ebp", "review", "soc", "ia"];

const WINDOW: Record<Exclude<DueWindow, "any">, number> = { "7d": 7, "14d": 14, "30d": 30 };

function matches(row: AuditIndexRowOut, query: AuditIndexQuery, today: string, tile: boolean) {
  if (query.segment !== undefined && row.segment !== query.segment) return false;
  if (tile && query.phase !== undefined && row.phase !== query.phase) return false;
  if (query.type !== undefined && row.engagement_type !== query.type) return false;
  if (query.office !== undefined && row.office_id !== query.office) return false;
  const due = query.due ?? "any";
  if (due !== "any") {
    if (row.report_due_on == null) return false;
    const left = days(today, row.report_due_on);
    if (left < 0 || left > WINDOW[due]) return false;
  }
  const q = query.q?.trim().toLowerCase();
  if (q && !`${row.name} ${row.client_name}`.toLowerCase().includes(q)) return false;
  return true;
}

function typeFacet(rows: readonly AuditIndexRowOut[]): Facet[] {
  const n = new Map<string, number>();
  for (const r of rows) n.set(r.engagement_type, (n.get(r.engagement_type) ?? 0) + 1);
  return [...n]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([value, count]) => ({ value, label: value, n: count }));
}

function summaryOf(rows: readonly AuditIndexRowOut[]): AuditIndexSummaryOut {
  const n = (f: (r: AuditIndexRowOut) => boolean) => rows.filter(f).length;
  return {
    ebp: n((r) => r.segment === "ebp"),
    fs_audit: n((r) => r.segment === "fs"),
    review: n((r) => r.engagement_type === "review"),
    compilation_preparation: n(
      (r) => r.engagement_type === "compilation" || r.engagement_type === "preparation",
    ),
    soc: n((r) => r.segment === "soc"),
    internal_audit: n((r) => r.segment === "ia"),
  };
}

/** The P-36 envelope for `GET /v1/audits` over the rows a viewer can see (after `visible()`). */
export function auditIndexPage(
  visible: readonly AuditIndexRowOut[],
  query: AuditIndexQuery,
  today: string,
  shown: readonly Segment[] = E0_SEGMENTS,
): AuditIndexPage {
  const items = visible.filter((r) => matches(r, query, today, true));
  // Tiles: every filter but the active tile (P-36 counts minus the active tile).
  const tileBase = visible.filter((r) => matches(r, query, today, false));
  const counts: Record<string, number> = {};
  for (const phase of TILE_PHASES)
    counts[phase] = tileBase.filter((r) => r.phase === phase).length;
  // Segments: every filter but the segment itself.
  const segmentBase = visible.filter((r) =>
    matches(r, { ...query, segment: undefined }, today, true),
  );
  const segments: Facet[] = shown.map((s) => ({
    value: s,
    label: s,
    n: segmentBase.filter((r) => r.segment === s).length,
  }));
  return {
    items,
    next_cursor: null,
    total: items.length,
    total_capped: false,
    counts,
    facets: { segment: segments, type: typeFacet(tileBase) },
    summary: summaryOf(tileBase),
  };
}

// --- Source Documents (AUD-02 canvas, AUD-03) ---------------------------------------------------

/** Northwind's six categories in the handoff's band order (AUD-02 and AUD-03 spec). */
export const NORTHWIND_CATEGORIES = [
  "Plan documents",
  "Trust / Recordkeeper Reports",
  "Census & Payroll",
  "Form 5500 & SOC 1",
  "Cash",
  "Compliance & other",
] as const;

type OwedBy = NonNullable<SourceDocumentRowOut["owed_by"]>;
// Who owes an open request, as the AUD-03 sub-lines name them: Dana is the plan's contact; Keystone's
// requests are delegated to Sam Ortiz (a third party); the other organisations answer directly.
const OWED_BY: Readonly<Record<string, OwedBy>> = {
  "Dana Kowalski": { kind: "client_contact", display: "Dana Kowalski" },
  "Keystone Retirement Services": { kind: "third_party", display: "Sam Ortiz, Keystone" },
};

// The files that answer Northwind's received and uploaded requests, verbatim from the AUD-02 spec's
// canvas (`initial-input/…`, `harborline-upload/…`). The Summary of net trust assets is the seeded
// Harborline document the viewer opens (seed/trust.ts); the others have no page images in fixtures.
const NORTHWIND_PATHS: Readonly<Record<string, string>> = {
  "Plan document & amendments": "initial-input/Northwind 401k Plan Document 2021 restatement.pdf",
  "Adoption agreement": "initial-input/Northwind Adoption Agreement 2024 amendment.pdf",
  "Summary plan description": "initial-input/Northwind SPD 2025.pdf",
  "Summary of net trust assets": "initial-input/Harborline Net Trust Assets 12-31-2025.pdf",
  "Schedule of Account Balances": "initial-input/Keystone Account Balances PY2025.xlsx",
  "Annual loan balance roll-forward": "initial-input/Keystone Loan Rollforward 2025.xlsx",
  "Brokerage / SDBA asset detail — BrokerWindow":
    "initial-input/BrokerWindow Asset Detail 2025.pdf",
  "Certified trust report (full year, signed)":
    "harborline-upload/Harborline Certification PY2025 signed.pdf",
  "Employee Census File": "initial-input/Northwind Census PY2025.xlsx",
  "Contribution Reports — PayGrid": "initial-input/PayGrid Contribution Detail 2025.xlsx",
  "Quarterly 941 Forms": "initial-input/941 Filings 2025 Q1-Q4.pdf",
  "SOC 1 Type 2 — Keystone Retirement Services":
    "initial-input/Keystone SOC1 Type2 Oct24-Sep25.pdf",
};

// The matcher's fulfilment confidence on each answered row, verbatim from the AUD-03 spec's
// sub-lines ("· matched 99%"); C5 v1.1 `match_confidence` (A-01-T10 populates it live).
const NORTHWIND_MATCHED: Readonly<Record<string, number>> = {
  "Plan document & amendments": 99,
  "Adoption agreement": 98,
  "Summary plan description": 99,
  "Certified trust report (full year, signed)": 94,
  "Summary of net trust assets": 99,
  "Schedule of Account Balances": 97,
  "Annual loan balance roll-forward": 98,
  "Brokerage / SDBA asset detail — BrokerWindow": 96,
  "Employee Census File": 99,
  "Contribution Reports — PayGrid": 97,
  "Quarterly 941 Forms": 99,
  "SOC 1 Type 2 — Keystone Retirement Services": 99,
};

// When an upload arrived where the spec dates it: the certified trust report "uploaded Sep 11";
// every other file came with the initial input on Sep 1.
const NORTHWIND_UPLOADED_ON: Readonly<Record<string, string>> = {
  "Certified trust report (full year, signed)": "2026-09-11",
};

/** The evidence version a row's file is: Harborline's is the seeded viewer document. */
export function northwindVersionId(title: string): string {
  return title === "Summary of net trust assets"
    ? stableId("evidence-version:northwind:harborline-net-trust-assets")
    : stableId(`evidence-version:northwind:${title}`);
}

export type SourceSort = "missing_first" | "received_first";

const MISSING_RANK: Readonly<Record<string, number>> = { uploaded: 0, requested: 1, received: 2 };

/** The work item's Source Documents aggregate from its requests: "Missing first" orders needs
 * review, requested, received inside each category; "Received first" the other way (stable). */
export function sourceDocuments(
  workItemId: string,
  binderId: string,
  requests: readonly RequestItemOut[],
  owners: Readonly<Record<string, string>>,
  today: string,
  sort: SourceSort = "missing_first",
): SourceDocumentsOut {
  const rank = (status: string): number => {
    const r = MISSING_RANK[status] ?? 1;
    return sort === "missing_first" ? r : -r;
  };
  const groups: SourceDocumentGroupOut[] = NORTHWIND_CATEGORIES.map((label) => {
    const rows: SourceDocumentRowOut[] = requests
      .filter((r) => r.audit_area === label)
      .map((r) => {
        const owner = owners[r.id];
        const open = r.status === "requested";
        return {
          request_item_id: r.id,
          binder_id: binderId,
          title: r.description,
          status: r.status,
          overdue: open && r.due_on != null && r.due_on < today,
          requested_at: r.created_at,
          due_on: r.due_on ?? null,
          owed_by:
            open && owner !== undefined
              ? (OWED_BY[owner] ?? { kind: "organisation", display: owner })
              : null,
          latest_upload:
            open || NORTHWIND_PATHS[r.description] === undefined
              ? null
              : {
                  evidence_version_id: northwindVersionId(r.description),
                  path_label: NORTHWIND_PATHS[r.description] ?? "",
                  uploaded_on: NORTHWIND_UPLOADED_ON[r.description] ?? r.created_at.slice(0, 10),
                  // The firm's initial input came in before the requests (AUD-03 a: no
                  // "uploaded" date); a client or its trustee uploaded the rest.
                  uploader_kind: (NORTHWIND_PATHS[r.description] ?? "").startsWith(
                    "initial-input/",
                  )
                    ? ("firm" as const)
                    : ("client" as const),
                },
          match_confidence: open ? null : (NORTHWIND_MATCHED[r.description] ?? null),
          linked_count: open ? null : 1,
          // AUD-03 R2: every answered file was screened and passed (b's card, Sep 11).
          screening: open ? null : ("passed" as const),
          returned_reason: null,
          allowed_actions: [],
        };
      })
      .map((row, i) => ({ row, i }))
      .sort((a, b) => rank(a.row.status) - rank(b.row.status) || a.i - b.i)
      .map(({ row }) => row);
    return {
      category_id: stableId(`category:${workItemId}:${label}`),
      label,
      received: rows.filter((r) => r.status === "received").length,
      total: rows.length,
      counted: true,
      rows,
    };
  });
  const all = groups.flatMap((g) => g.rows ?? []);
  return {
    work_item_id: workItemId,
    received: all.filter((r) => r.status === "received").length,
    total: all.length,
    needs_review: all.filter((r) => r.status === "uploaded").length,
    requested: all.filter((r) => r.status === "requested").length,
    groups,
  };
}

// --- Wave 7 (AUD-01 g, h; E2) -------------------------------------------------------------------

/** The E2 instant AUD-01 g and h stand at: Mon Sep 14, 2026, 10:30 AM CT (revision R2). */
export const WAVE7_INSTANT = "2026-09-14T10:30:00-05:00";

interface Wave7Row {
  name: string;
  client: string;
  type: AuditIndexRowOut["engagement_type"];
  segment: Segment;
  group?: true;
  period: string;
  phase: AuditEngagementStatus;
  epMgr: string;
  office: IndexFacts["office"];
  due: string | null;
  pbc?: readonly [number, number];
  tag?: string;
  released?: string;
}

// A28–A33, verbatim from AUD-01 revision.md g (blueprint §9.10). Fixture only: they are created
// live by A-09, X-01 and X-03 under their entitlements. The contract has no report type, programme
// or drafted-PBC count yet (DEC-340), so Type and PBC read from the fields it does carry.
const WAVE7: readonly Wave7Row[] = [
  {
    name: "Harlow & Pike Holdings, Inc.",
    client: "Harlow & Pike Holdings, Inc.",
    type: "fs_audit",
    segment: "fs",
    group: true,
    period: "FYE 12/31/2026",
    phase: "planning",
    epMgr: "MO / OH",
    office: "Chicago",
    due: "2027-03-19",
    tag: "Component auditor",
  },
  {
    name: "Larkfield Payroll Services",
    client: "Larkfield Payroll Services",
    type: "soc1",
    segment: "soc",
    period: "Jan 1 – Dec 31, 2026",
    phase: "planning",
    epMgr: "CM / LK",
    office: "New York",
    due: null,
  },
  {
    name: "Prairie Lakes Community Bank",
    client: "Prairie Lakes Community Bank",
    type: "internal_audit",
    segment: "ia",
    period: "FY2026",
    phase: "planning",
    epMgr: "PR / LK",
    office: "Denver",
    due: null,
  },
  {
    name: "Tessellate Health Cloud, Inc.",
    client: "Tessellate Health Cloud, Inc.",
    type: "soc2",
    segment: "soc",
    period: "Oct 1, 2025 – Sep 30, 2026",
    phase: "fieldwork",
    epMgr: "CM / LK",
    office: "Denver",
    due: "2026-11-13",
    pbc: [186, 212],
    tag: "3 exceptions",
  },
  {
    name: "Ashford Manufacturing Co.",
    client: "Ashford Manufacturing Co.",
    type: "internal_audit",
    segment: "ia",
    period: "FY2026",
    phase: "fieldwork",
    epMgr: "PR / LK",
    office: "Chicago",
    due: null,
    tag: "9 issues · 2 overdue",
  },
  {
    name: "Brightline Telehealth",
    client: "Brightline Telehealth",
    type: "soc2",
    segment: "soc",
    period: "as of Jun 30, 2026",
    phase: "released",
    epMgr: "CM / LK",
    office: "New York",
    due: null,
    released: "2026-08-21",
  },
];

/** The six wave-7 rows at `today`; `clientIdOf` keeps a seeded client's id (Ashford's wall). */
export function wave7Rows(today: string, clientIdOf: (name: string) => string): AuditIndexRow[] {
  return WAVE7.map((w) => {
    const [partner, manager] = w.epMgr.split(" / ");
    return {
      work_item_id: stableId(`work-item:wave7:${w.name}`),
      engagement_id: stableId(`engagement:wave7:${w.name}`),
      client_id: clientIdOf(w.client),
      client_name: w.client,
      name: w.name,
      engagement_type: w.type,
      segment: w.segment,
      ebp_plan_kind: null,
      limited_scope_103a3c: false,
      is_group_audit: w.group === true,
      period_label: w.period,
      phase: w.phase,
      released_on: w.released ?? null,
      run_badge: null,
      tags:
        w.tag === undefined
          ? []
          : [{ source: "wave7", code: slugOf(w.tag), text: w.tag, classification: "content" }],
      pbc: w.pbc === undefined ? null : { received: w.pbc[0], total: w.pbc[1] },
      partner_initials: partner ?? null,
      manager_initials: manager ?? null,
      office_id: officeIdOf(w.office),
      office_name: w.office,
      report_due_on: w.due,
      report_due_tone: tone(w.due, today),
      archive:
        w.released === undefined
          ? null
          : {
              state: "archiving",
              days_left: days(today, addDays(w.released, ARCHIVE_DAYS)),
              firm_tool_ref: null,
            },
      allowed_actions: [],
    };
  });
}

type AuditIndexRow = AuditIndexRowOut;

/** Rows in the server's order: tile order, then report due (none last), then name. */
export function sortAuditRows(rows: readonly AuditIndexRowOut[]): AuditIndexRowOut[] {
  const tileOrder = (p: AuditEngagementStatus) => TILE_PHASES.indexOf(p);
  return [...rows].sort(
    (a, b) =>
      tileOrder(a.phase) - tileOrder(b.phase) ||
      (a.report_due_on ?? "9999").localeCompare(b.report_due_on ?? "9999") ||
      a.name.localeCompare(b.name),
  );
}
