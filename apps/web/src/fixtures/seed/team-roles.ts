// ENG-05's teams (P-07-T39; docs/screens/ENG-05.md): the roster `GET …/team` answers
// (`TeamRosterMemberOut`), the team approval (`TeamApprovalOut`), the EQR candidates
// (`EqrCandidateOut`) and the people "+ Add person" offers, typed with the generated client.
// Names, roles, hours and dates are verbatim from the ENG-05 canvas (`Wave 3 - Engagements &
// Projects.dc.html#eng05`, E5.V):
//
//   Northwind  PY2025 EBP Audit (A1): MO EP · TW EQR · HL · MD · AC confirmed; Kira Ross proposed
//              Sep 11 and pending. Budget 10 + 6 + 37 + 61 + 40 + 18 = 172.0; actuals 1 + 0 + 7 +
//              12 + 4 = 24.0 (ENG-06's figures; the roster carries no actuals until I-04).
//   Fairhaven  PY2025 EBP Audit (A7), Accepted: MO EP · CM EQR · LK · CD confirmed, FN pending;
//              Thomas Whitcombe was EP on this plan for PY2024 (cooling-off).
//   Granite    PY2026 EBP Audit for Granite Peak Outdoor Supply 401(k) Plan, created today,
//              Prospect, no team.
//
// The EQR's eligibility approval (Celia Marsh, QM delegate, Jun 1, 2026) has no read route yet
// (docs/screens/ENG-05.md, Open gaps); it is not served here.

import type {
  CandidateOut,
  EngagementRecordOut,
  EqrCandidateOut,
  TeamApprovalOut,
  TeamRosterMemberOut,
} from "@abacus/api-client";
import type { Seed } from ".";
import { entityIdOf, slugOfClient } from "./clients";
import { type EngagementRecordFixture, engagementRecords } from "./engagement-records";
import { slugOf } from "./people";
import { stableId } from "./prng";

export function userIdOf(name: string): string {
  return stableId(`user:${slugOf(name)}`);
}

type Role = TeamRosterMemberOut["role"];

interface TeamRow {
  name: string;
  role: Role;
  /** Budget hours, one decimal, as the server's decimal string. */
  budget: string;
  /** ENG-06's actual hours (I-04); null where the canvas draws "—". Not on the roster. */
  actual: string | null;
  /** The day the person confirmed independence here, or null while pending. */
  confirmed: string | null;
  portal: boolean;
  /** When the person was proposed (after the team approval), or null. */
  proposed?: string;
}

const T = (
  name: string,
  role: Role,
  budget: string,
  actual: string | null,
  confirmed: string | null,
  portal: boolean,
  proposed?: string,
): TeamRow => ({
  name,
  role,
  budget,
  actual,
  confirmed,
  portal,
  ...(proposed === undefined ? {} : { proposed }),
});

/** Northwind PY2025 EBP Audit at E0 (ENG-05 a). */
export const NORTHWIND_TEAM: readonly TeamRow[] = [
  T("Margaret Okonkwo", "engagement_partner", "10.0", "1.0", "2026-06-01", true),
  T("Thomas Whitcombe", "eqr_reviewer", "6.0", "0.0", "2026-06-01", false),
  T("Hannah Leclerc", "manager", "37.0", "7.0", "2026-05-29", true),
  T("Marcus Delaney", "senior", "61.0", "12.0", "2026-05-29", true),
  T("Ana Cruz", "staff", "40.0", "4.0", "2026-06-03", false),
  T("Kira Ross", "staff", "18.0", null, null, false, "2026-09-11T14:20:00Z"),
];

/** Fairhaven PY2025 EBP Audit (ENG-05 c). */
export const FAIRHAVEN_TEAM: readonly TeamRow[] = [
  T("Margaret Okonkwo", "engagement_partner", "8.0", "0.5", "2026-09-08", true),
  T("Celia Marsh", "eqr_reviewer", "5.0", "0.0", "2026-09-08", false),
  T("Laura Kemp", "manager", "30.0", "2.0", "2026-09-08", true),
  T("Caleb Dunn", "senior", "52.0", "1.5", "2026-09-09", true),
  T("Fiona Nash", "staff", "36.0", null, null, false),
];

export function rosterOf(team: readonly TeamRow[]): TeamRosterMemberOut[] {
  return team.map((m) => ({
    user_id: userIdOf(m.name),
    display_name: m.name,
    role: m.role,
    budget_hours: m.budget,
    shown_on_portal: m.portal,
    proposed_at: m.proposed ?? null,
    independence: m.confirmed === null ? "requested" : "confirmed",
  }));
}

/** ENG-06's actual hours for a team (the footing test; the screen shows "—" until I-04). */
export function actualsOf(team: readonly TeamRow[]): readonly (string | null)[] {
  return team.map((m) => m.actual);
}

const HASH = (key: string): string => stableId(`team-hash:${key}`).replaceAll("-", "");

export function northwindApproval(engagementId: string): TeamApprovalOut {
  return {
    engagement_id: engagementId,
    member_set_hash: HASH("northwind"),
    approved_by: userIdOf("Margaret Okonkwo"),
    approved_by_name: "Margaret Okonkwo",
    approved_at: "2026-06-01T15:00:00Z",
    changed: true,
    added_since: [userIdOf("Kira Ross")],
  };
}

export function fairhavenApproval(engagementId: string): TeamApprovalOut {
  return {
    engagement_id: engagementId,
    member_set_hash: HASH("fairhaven"),
    approved_by: userIdOf("Margaret Okonkwo"),
    approved_by_name: "Margaret Okonkwo",
    approved_at: "2026-09-08T15:00:00Z",
    changed: false,
    added_since: [],
  };
}

export function emptyApproval(engagementId: string): TeamApprovalOut {
  return {
    engagement_id: engagementId,
    member_set_hash: HASH("empty"),
    approved_by: null,
    approved_by_name: null,
    approved_at: null,
    changed: false,
    added_since: [],
  };
}

/** Northwind's EQR candidates: Thomas Whitcombe (current) and Celia Marsh, both eligible. */
export const NORTHWIND_EQR: readonly EqrCandidateOut[] = [
  {
    user_id: userIdOf("Thomas Whitcombe"),
    display_name: "Thomas Whitcombe",
    eligibility: "eligible",
    current: true,
    checks: [
      { code: "not_on_team", result: "pass" },
      { code: "cooling_off", result: "pass" },
      { code: "competence", result: "pass", count: 3, year: 2025 },
      { code: "independence", result: "pass" },
      { code: "capacity", result: "not_assessed" },
    ],
  },
  {
    user_id: userIdOf("Celia Marsh"),
    display_name: "Celia Marsh",
    eligibility: "eligible",
    checks: [
      { code: "not_on_team", result: "pass" },
      { code: "cooling_off", result: "pass" },
      { code: "competence", result: "pass", count: 1, year: 2025 },
      { code: "independence", result: "pass" },
      { code: "capacity", result: "not_assessed" },
    ],
  },
];

/** Fairhaven's: Celia Marsh (current) and Thomas Whitcombe, EP on this plan for PY2024. */
export const FAIRHAVEN_EQR: readonly EqrCandidateOut[] = [
  {
    user_id: userIdOf("Celia Marsh"),
    display_name: "Celia Marsh",
    eligibility: "eligible",
    current: true,
    checks: [
      { code: "not_on_team", result: "pass" },
      { code: "cooling_off", result: "pass" },
      { code: "competence", result: "pass", count: 1, year: 2025 },
      { code: "independence", result: "pass" },
      { code: "capacity", result: "not_assessed" },
    ],
  },
  {
    user_id: userIdOf("Thomas Whitcombe"),
    display_name: "Thomas Whitcombe",
    eligibility: "not_eligible",
    checks: [
      { code: "not_on_team", result: "pass" },
      { code: "cooling_off", result: "fail", year: 2024 },
      { code: "competence", result: "pass", count: 3, year: 2025 },
      { code: "independence", result: "pass" },
      { code: "capacity", result: "not_assessed" },
    ],
  },
];

/** "+ Add person" (the canvas's pool): with an EP on the team, the audit staff not on it. */
export const ADD_POOL: readonly string[] = [
  "Kira Ross",
  "Jasper Bell",
  "Cole Hart",
  "Simone Baptiste",
];
/** Without an EP (e): the partners who can lead it. */
export const PARTNER_POOL: readonly string[] = [
  "Margaret Okonkwo",
  "Thomas Whitcombe",
  "Celia Marsh",
];

export function candidatesOf(names: readonly string[]): CandidateOut[] {
  return names.map((n) => ({ user_id: userIdOf(n), display_name: n }));
}

const ENG05_ACTIONS = [
  "engagement.read_metadata",
  "engagement.read",
  "engagement.member_add",
  "engagement.member_remove",
  "engagement.update",
  "eqr.assign",
  "independence.remind",
];

/** Northwind's ENG-02 record with what a manager on it may do on the Team tab. */
export function northwindRecord(seed: Seed): EngagementRecordFixture {
  const base = engagementRecords(seed).b;
  return {
    ...base,
    record: {
      ...base.record,
      allowed_actions: ENG05_ACTIONS,
      tab_counts: { ...base.record.tab_counts, team: 6 },
    },
  };
}

function client(name: string): string {
  return stableId(`client:${slugOfClient(name)}`);
}

/** Fairhaven's record (c): Accepted, the letter out, G1 met Aug 28. */
export function fairhavenRecord(seed: Seed): EngagementRecordFixture {
  const name = "Fairhaven Foods 401(k) Plan";
  const id = seed.engagementIds.A7 ?? stableId("engagement:fairhaven:py2025");
  const record: EngagementRecordOut = {
    id,
    name: "PY2025 EBP Audit",
    client_id: client(name),
    client_name: name,
    client_entity_id: entityIdOf(slugOfClient(name), name),
    client_entity_name: name,
    type: "ebp_audit",
    service_line: "audit",
    status: "accepted",
    period_label: "PY2025",
    fiscal_period_start: "2025-01-01",
    fiscal_period_end: "2025-12-31",
    bands: [],
    contacts: [],
    letter: { status: "not_signed", signed_count: 0, signer_count: 2 },
    gates: [
      {
        gate: "G1",
        met: true,
        met_at: "2026-08-28T15:00:00Z",
        met_by_user_id: userIdOf("Margaret Okonkwo"),
      },
      { gate: "G2", met: false },
      { gate: "G3", met: false },
    ],
    tab_counts: { work_items: 1, team: 5 },
    read_only_reason: null,
    version: 3,
    allowed_actions: ENG05_ACTIONS,
  };
  return { record, workItems: [], acceptanceDecidedAt: "2026-08-28T15:00:00Z", team: [] };
}

/** Granite Peak's plan audit (e): created today, Prospect, no team. */
export function granitePlanRecord(): EngagementRecordFixture {
  const sponsor = "Granite Peak Outdoor Supply, Inc.";
  const plan = "Granite Peak Outdoor Supply 401(k) Plan";
  const id = stableId("engagement:granite-peak:py2026-ebp");
  const record: EngagementRecordOut = {
    id,
    name: "PY2026 EBP Audit",
    client_id: client(sponsor),
    client_name: sponsor,
    client_entity_id: entityIdOf(slugOfClient(sponsor), plan),
    client_entity_name: plan,
    type: "ebp_audit",
    service_line: "audit",
    status: "prospect",
    period_label: "PY2026",
    fiscal_period_start: "2026-01-01",
    fiscal_period_end: "2026-12-31",
    bands: [],
    contacts: [],
    letter: { status: "not_signed", signed_count: 0, signer_count: 0 },
    gates: [
      { gate: "G1", met: false },
      { gate: "G2", met: false },
      { gate: "G3", met: false },
    ],
    tab_counts: { work_items: 0, team: 0 },
    read_only_reason: null,
    version: 1,
    allowed_actions: ENG05_ACTIONS,
  };
  return { record, workItems: [], acceptanceDecidedAt: null, team: [] };
}
