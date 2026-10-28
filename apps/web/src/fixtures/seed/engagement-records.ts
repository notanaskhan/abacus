// ENG-02's engagement records (P-07-T20; docs/screens/ENG-02.md): the v2 record projection
// (`EngagementRecordOut`) for the artboards P-07-T20 builds, typed with the generated client.
// Names, figures and dates are verbatim from the handoff (ENG-02 spec.md b, c, d; ENG-01 spec.md
// rows 9 and 16 for Bluestem and the Thornbury estate) and blueprint §3.3.2 for the gates.
//
//   b         Northwind Robotics 401(k) Plan "PY2025 EBP Audit", Active: G1–G3 met, G4 blocked
//   c         Bluestem Analytics, LLC "2026 Close (from Oct)", Accepted, letter viewed Sep 11
//   d         Meridian Tool & Die, Inc. "FY2025 FS Audit", Archived, locked Jun 12, 2026 (WORM)
//   prospect  Estate of Walter Thornbury "Estate returns — final 1040 · 1041 · 706", Prospect, with
//             the intake's three work items (Form 706, Form 1041, Form 1040; P-07-T62)
//
//   a, g      Copperleaf Coffee Roasters, Inc. "2026 Close", Active, CAS (P-07-T28): its 12 closes
//   f         Granite Peak "FY2026 Financial Statement Audit" at Oct 6 (P-07-T28; the Dashboard tab)
//
// Rail rows carry the record's own words (`text`), dates
// (`on`), people (`user_id`) and pills; the gate facts are the gate payload (met, met_at, met_by,
// blockers), never sentences (docs/screens/ENG-02.md, Deviations).

import type {
  EngagementGateOut,
  EngagementRailBandOut,
  EngagementRecordOut,
  TeamMemberOut,
  WorkItemOut,
} from "@abacus/api-client";
import type { Seed } from ".";
import { entityIdOf, slugOfClient } from "./clients";
import { slugOf } from "./people";
import { stableId } from "./prng";

export const ENG_NORTHWIND = "PY2025 EBP Audit";
export const ENG_BLUESTEM = "2026 Close (from Oct)";
export const ENG_MERIDIAN = "FY2025 FS Audit";
export const ENG_THORNBURY = "Estate returns — final 1040 · 1041 · 706";
export const ENG_COPPERLEAF = "2026 Close";
export const ENG_GRANITE_PEAK_OCT6 = "FY2026 Financial Statement Audit";

export interface EngagementRecordFixture {
  record: EngagementRecordOut;
  workItems: WorkItemOut[];
  /** When the acceptance decision was made (G1), for the recorded-letter date rule. */
  acceptanceDecidedAt: string | null;
  /** `GET …/team` (the Team tab host); absent, the seed engagement's team. */
  team?: TeamMemberOut[];
}

function user(name: string): string {
  return stableId(`user:${slugOf(name)}`);
}

function client(name: string): string {
  return stableId(`client:${slugOfClient(name)}`);
}

const ALL_GATES = ["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9"] as const;

function gates(
  met: Record<string, { at: string; by?: string }>,
  blocked: Record<string, string> = {},
  only?: readonly string[],
): EngagementGateOut[] {
  return (only ?? ALL_GATES).map((gate) => {
    const m = met[gate];
    const reason = blocked[gate];
    const g = gate as EngagementGateOut["gate"];
    if (m !== undefined) {
      return {
        gate: g,
        met: true,
        met_at: m.at,
        met_by_user_id: m.by === undefined ? null : user(m.by),
      };
    }
    if (reason !== undefined) {
      return {
        gate: g,
        met: false,
        blockers: [
          { type: "decision", id: stableId(`blocker:${gate}:${reason}`), reason_code: reason },
        ],
      };
    }
    return { gate: g, met: false };
  });
}

function band(
  name: EngagementRailBandOut["band"],
  rows: EngagementRailBandOut["rows"],
): EngagementRailBandOut {
  return { band: name, rows };
}

// ---- b: Northwind -------------------------------------------------------------------------------

function northwind(seed: Seed): EngagementRecordFixture {
  const id = seed.engagementIds.A1 ?? stableId("engagement:northwind:py2025");
  const sponsor = "Northwind Robotics, Inc.";
  const plan = "Northwind Robotics 401(k) Plan";
  const record: EngagementRecordOut = {
    id,
    name: ENG_NORTHWIND,
    client_id: client(sponsor),
    client_name: sponsor,
    client_entity_id: entityIdOf(slugOfClient(sponsor), plan),
    client_entity_name: plan,
    type: "ebp_audit",
    service_line: "audit",
    status: "active",
    period_label: "PY2025",
    fiscal_period_start: "2025-01-01",
    fiscal_period_end: "2025-12-31",
    bands: [
      band("details", [
        { key: "client", text: "Northwind Robotics, Inc. (plan sponsor)" },
        { key: "entity", text: "Northwind Robotics 401(k) Plan · PN 001" },
        { key: "type", text: "EBP DC · §103(a)(3)(C)" },
        { key: "standards", text: "GAAS nonissuer · AU-C 703" },
        { key: "methodology", text: "BH Audit Methodology · EBP v3" },
        { key: "office", text: "Chicago" },
        { key: "letter", on: "2026-06-02", pill_object: "letter_record", pill_code: "signed" },
        { key: "fee", text: "$32,000 fixed" },
      ]),
    ],
    contacts: [
      {
        designation: "ske_designee",
        contact_id: stableId("contact:northwind:dana-kowalski"),
        name: "Dana Kowalski",
      },
      {
        designation: "signing_officer",
        contact_id: stableId("contact:northwind:dana-kowalski"),
        name: "Dana Kowalski",
      },
    ],
    letter: { status: "signed", signed_on: "2026-06-02", signed_count: 2, signer_count: 2 },
    gates: gates(
      {
        G1: { at: "2026-05-28T15:00:00Z", by: "Margaret Okonkwo" },
        G2: { at: "2026-06-01T15:00:00Z" },
        G3: { at: "2026-06-02T15:00:00Z", by: "Margaret Okonkwo" },
      },
      { G4: "partner_decision" },
    ),
    tab_counts: { work_items: 1, team: 5 },
    read_only_reason: null,
    version: 12,
    allowed_actions: ["engagement.read_metadata", "engagement.read"],
  };
  const workItems: WorkItemOut[] =
    (seed.workItems[id] ?? []).length > 0
      ? (seed.workItems[id] ?? [])
      : [
          {
            id: stableId("work-item:northwind:py2025"),
            kind: "assurance",
            name: "PY2025 Employee Benefit Plan Audit",
            phase: "planning",
            status: "active",
            due_on: "2026-10-15",
            period_start: "2025-01-01",
            period_end: "2025-12-31",
          },
        ];
  return { record, workItems, acceptanceDecidedAt: "2026-05-28T15:00:00Z" };
}

// ---- c: Bluestem --------------------------------------------------------------------------------

function bluestem(): EngagementRecordFixture {
  const name = "Bluestem Analytics, LLC";
  const id = stableId("engagement:bluestem:2026-close-from-oct");
  const record: EngagementRecordOut = {
    id,
    name: ENG_BLUESTEM,
    client_id: client(name),
    client_name: name,
    client_entity_id: entityIdOf(slugOfClient(name), name),
    client_entity_name: name,
    type: "cas_monthly_close",
    service_line: "cas",
    status: "accepted",
    period_label: "Oct–Dec 2026",
    fiscal_period_start: "2026-10-01",
    fiscal_period_end: "2026-12-31",
    bands: [
      band("details", [
        { key: "client", text: name },
        { key: "period", text: "Oct–Dec 2026" },
        { key: "office", text: "New York" },
        { key: "letter", pill_object: "letter_record", pill_code: "not_signed" },
      ]),
      band("review_delivery", [{ key: "partner", user_id: user("Priya Raman") }]),
    ],
    contacts: [
      {
        designation: "signing_officer",
        contact_id: stableId("contact:bluestem:arjun-mehta"),
        name: "Arjun Mehta",
      },
    ],
    letter: {
      status: "not_signed",
      last_event: "viewed",
      last_event_on: "2026-09-11",
      signed_count: 0,
      signer_count: 2,
    },
    gates: gates(
      {
        G1: { at: "2026-09-08T15:00:00Z", by: "Priya Raman" },
        G2: { at: "2026-09-08T15:00:00Z" },
      },
      { G3: "letter_not_signed" },
      ["G1", "G2", "G3"],
    ),
    tab_counts: { work_items: 0, team: 2 },
    read_only_reason: null,
    version: 3,
    allowed_actions: ["engagement.read_metadata", "engagement.read", "letter.record"],
  };
  return { record, workItems: [], acceptanceDecidedAt: "2026-09-08T15:00:00Z" };
}

// ---- d: Meridian --------------------------------------------------------------------------------

function meridian(seed: Seed): EngagementRecordFixture {
  const name = "Meridian Tool & Die, Inc.";
  const id = seed.engagementIds.A20 ?? stableId("engagement:meridian:fy2025");
  const met = Object.fromEntries(
    ALL_GATES.map((g) => [g, { at: "2026-06-12T15:00:00Z", by: "Margaret Okonkwo" }]),
  );
  const record: EngagementRecordOut = {
    id,
    name: ENG_MERIDIAN,
    client_id: client(name),
    client_name: name,
    client_entity_id: entityIdOf(slugOfClient(name), name),
    client_entity_name: name,
    type: "fs_audit",
    service_line: "audit",
    status: "archived",
    period_label: "FY2025",
    fiscal_period_start: "2025-01-01",
    fiscal_period_end: "2025-12-31",
    bands: [
      band("details", [
        { key: "client", text: name },
        { key: "office", text: "Chicago" },
        { key: "archive_locked", on: "2026-06-12" },
        { key: "post_lock_additions", text: "0" },
      ]),
    ],
    contacts: [],
    letter: { status: "signed", signed_count: 2, signer_count: 2 },
    gates: gates(met),
    tab_counts: { work_items: (seed.workItems[id] ?? []).length, team: 4 },
    read_only_reason: "archived",
    version: 40,
    allowed_actions: ["engagement.read_metadata", "engagement.read"],
  };
  return { record, workItems: seed.workItems[id] ?? [], acceptanceDecidedAt: null };
}

// ---- prospect: the Thornbury estate -------------------------------------------------------------

function thornbury(): EngagementRecordFixture {
  const name = "Estate of Walter Thornbury";
  const id = stableId("engagement:thornbury-estate:estate-returns");
  const record: EngagementRecordOut = {
    id,
    name: ENG_THORNBURY,
    client_id: client(name),
    client_name: name,
    client_entity_id: entityIdOf(slugOfClient(name), name),
    client_entity_name: name,
    type: "tax_compliance",
    service_line: "tax",
    status: "prospect",
    period_label: "2026–2027",
    fiscal_period_start: "2026-01-01",
    fiscal_period_end: "2027-01-31",
    bands: [
      band("details", [
        { key: "client", text: name },
        { key: "period", text: "2026–2027" },
        { key: "office", text: "Chicago" },
      ]),
      band("review_delivery", [{ key: "partner", user_id: user("Daniel Reyes") }]),
    ],
    contacts: [],
    letter: { status: "not_signed", signed_count: 0, signer_count: 0 },
    gates: gates({}, { G1: "acceptance_pending" }, ["G1", "G2", "G3"]),
    tab_counts: { work_items: 3, team: 1 },
    read_only_reason: null,
    version: 1,
    allowed_actions: ["engagement.read_metadata", "engagement.read"],
  };
  // The intake commit's work items (DEC-430; P-07-T62's j19 3): one tax return per form, named
  // as the live commit names them ("Form ‹FORM›").
  const workItems: WorkItemOut[] = (
    [
      ["706", "2026-02-02", "2026-02-02"],
      ["1041", "2026-02-02", "2027-01-31"],
      ["1040", "2026-01-01", "2026-02-02"],
    ] as const
  ).map(([form, start, end]) => ({
    id: stableId(`work-item:thornbury-estate:${form}`),
    kind: "tax_return",
    name: `Form ${form}`,
    period_start: start,
    period_end: end,
    due_on: null,
    phase: null,
    status: "active",
  }));
  return { record, workItems, acceptanceDecidedAt: null };
}

// ---- a, g: Copperleaf ---------------------------------------------------------------------------

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;

/** The close's phase in month order: January–June Locked, July Delivered ("7 of 12" delivered),
 * August In progress (4 days past due), September–December Not started (spec.md a). */
function closePhase(month: number): string {
  if (month < 6) return "locked";
  if (month === 6) return "delivered";
  if (month === 7) return "in_progress";
  return "not_started";
}

function copperleaf(): EngagementRecordFixture {
  const name = "Copperleaf Coffee Roasters, Inc.";
  const id = stableId("engagement:copperleaf:2026-close");
  const record: EngagementRecordOut = {
    id,
    name: ENG_COPPERLEAF,
    client_id: client(name),
    client_name: name,
    client_entity_id: entityIdOf(slugOfClient(name), name),
    client_entity_name: name,
    type: "cas_monthly_close",
    service_line: "cas",
    status: "active",
    period_label: "Jan–Dec 2026",
    fiscal_period_start: "2026-01-01",
    fiscal_period_end: "2026-12-31",
    bands: [
      band("details", [
        { key: "client", text: name },
        { key: "entity", text: "S corporation (1120-S)" },
        { key: "service", text: "Client accounting services (non-attest)" },
        { key: "period", text: "Jan–Dec 2026" },
        { key: "office", text: "Denver" },
        { key: "close_plan", text: "Café with Square/Shopify" },
        { key: "letter", on: "2026-03-03", pill_object: "letter_record", pill_code: "signed" },
        { key: "fee", text: "$3,200 per month, fixed" },
      ]),
      band("review_delivery", [
        { key: "due_date", text: "10th of the following month" },
        { key: "partner", user_id: user("Priya Raman") },
        { key: "preparer", user_id: user("Raj Malhotra") },
        { key: "client_service", user_id: user("Grace Holloway") },
      ]),
      band("client_portal", [
        { key: "contact", text: "Tess Moreno · Owner" },
        { key: "approver_of_record", text: "Ben Ashby · Controller" },
        { key: "portal", text: "Active" },
        { key: "connections", text: "QuickBooks Online ✓ · Front Range Bank ••4410 ✓" },
        { key: "reminder", text: "Draft Email" },
      ]),
    ],
    contacts: [
      {
        designation: "approver_of_record",
        contact_id: stableId("contact:copperleaf:ben-ashby"),
        name: "Ben Ashby",
      },
    ],
    letter: { status: "signed", signed_on: "2026-03-03", signed_count: 2, signer_count: 2 },
    // Non-attest: G1 and G3 (gate_policy.py). The handoff dates only the letter (Mar 3).
    gates: [
      { gate: "G1", met: true },
      { gate: "G3", met: true, met_at: "2026-03-03T15:00:00Z" },
    ],
    tab_counts: { work_items: 12, team: 3 },
    read_only_reason: null,
    version: 9,
    // Priya Raman is Copperleaf's engagement partner: the status pill's ⌄ menu (DEC-344).
    allowed_actions: ["engagement.read_metadata", "engagement.read", "engagement.hold"],
  };
  const workItems: WorkItemOut[] = MONTHS.map((month, i) => {
    const mm = String(i + 1).padStart(2, "0");
    const last = new Date(Date.UTC(2026, i + 1, 0)).getUTCDate();
    const due = new Date(Date.UTC(2026, i + 1, 10)).toISOString().slice(0, 10);
    return {
      id: stableId(`work-item:copperleaf:2026-${mm}`),
      kind: "close",
      name: `${month} 2026 Close`,
      phase: closePhase(i),
      status: "active",
      due_on: due,
      period_start: `2026-${mm}-01`,
      period_end: `2026-${mm}-${String(last)}`,
    };
  });
  const team: TeamMemberOut[] = [
    { user_id: user("Priya Raman"), display_name: "Priya Raman", role: "engagement_partner" },
    { user_id: user("Raj Malhotra"), display_name: "Raj Malhotra", role: "senior" },
    { user_id: user("Grace Holloway"), display_name: "Grace Holloway", role: "client_service" },
  ];
  return { record, workItems, acceptanceDecidedAt: null, team };
}

// ---- f: Granite Peak at Oct 6 -------------------------------------------------------------------

/** f stands at Tue Oct 6, 2026 (revision R2): Granite Peak's FY2026 audit, Active by then. The
 * Dashboard tab's content is ENG-12's (K-04), so the record carries only what the subbar and
 * rail need. */
export function granitePeakOct6(seed: Seed): EngagementRecordFixture {
  const name = "Granite Peak Outdoor Supply, Inc.";
  const id = seed.engagementIds.A2 ?? stableId("engagement:granite-peak:fy2026");
  const record: EngagementRecordOut = {
    id,
    name: ENG_GRANITE_PEAK_OCT6,
    client_id: client(name),
    client_name: name,
    client_entity_id: entityIdOf(slugOfClient(name), name),
    client_entity_name: name,
    type: "fs_audit",
    service_line: "audit",
    status: "active",
    period_label: "FYE 6/30/2026",
    fiscal_period_start: "2025-07-01",
    fiscal_period_end: "2026-06-30",
    bands: [
      band("details", [
        { key: "client", text: name },
        { key: "office", text: "Denver" },
        { key: "letter", pill_object: "letter_record", pill_code: "signed" },
      ]),
      band("review_delivery", [{ key: "partner", user_id: user("Margaret Okonkwo") }]),
    ],
    contacts: [],
    letter: { status: "signed", signed_count: 2, signer_count: 2 },
    gates: [
      { gate: "G1", met: true },
      { gate: "G2", met: true },
      { gate: "G3", met: true },
    ],
    tab_counts: { work_items: 1, team: 0 },
    read_only_reason: null,
    version: 1,
    allowed_actions: ["engagement.read_metadata", "engagement.read"],
  };
  return { record, workItems: seed.workItems[id] ?? [], acceptanceDecidedAt: null, team: [] };
}

export type EngagementRecordKey = "a" | "b" | "c" | "d" | "prospect";

export function engagementRecords(
  seed: Seed,
): Record<EngagementRecordKey, EngagementRecordFixture> {
  return {
    a: copperleaf(),
    b: northwind(seed),
    c: bluestem(),
    d: meridian(seed),
    prospect: thornbury(),
  };
}
