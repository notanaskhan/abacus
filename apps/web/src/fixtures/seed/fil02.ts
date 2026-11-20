// FIL-02 fixture data (Q-05-T21, TASK-8827; handoff FIL-02): Felix Andersen (Firm Admin) at Mon
// Sep 14, 2026 9:24 AM CT; f is Samuel Ito (Staff), read-only. Words and figures from the handoff.
import { stableId } from "./prng";

export type Fil02State = "a" | "b" | "c" | "d" | "e" | "f" | "g" | "h" | "i";
const POLICIES = [
  ["signed_efile_authorization", 3, 7, "filing_date", false],
  ["tax_return", 3, 7, "filing_date", false],
  ["tax_workbook", 3, 7, "filing_date", false],
  ["audit_documentation", 5, 7, "report_release", true],
  ["cas_workpapers", 7, 7, "period_end", false],
  ["engagement_letter", 7, 7, "relationship_end", false],
  ["permanent_file", 7, 7, "client_inactive", false],
  ["message", 7, 7, "message_date", false],
] as const;

export function policies() {
  return {
    items: POLICIES.map(([record_type, floor, years, anchor, lock]) => ({
      record_type, service_line: "any", firm_years: String(years), legal_floor_years: String(floor),
      clock_start_event: anchor, anchor, lock, basis: null, authority: null, source: "firm", version: 1,
    })), // prettier-ignore
  };
}

export function summary(state: Fil02State) {
  return {
    policies: 8, active_holds: 2,
    pending_batches: state === "i" ? 0 : 1,
    pending_documents: state === "e" ? 1201 : 1204,
    last_certificate_ref: state === "i" ? "DC-2026-Q3" : "DC-2026-Q2",
    last_certificate_at: state === "i" ? "2026-09-14T09:40:00-05:00" : "2026-06-30T17:00:00-05:00",
  }; // prettier-ignore
}

export function holds() {
  return {
    items: [
      ["Collins CP2000 TY2023", "irs_examination", "Victor Hammond", "2026-08-12", 2023],
      ["Meridian IL-1120 TY2024", "state_controversy", "Neil Ashcroft", "2026-08-14", 2024],
    ].map(([name, reason, by, since, year]) => ({
      id: stableId(`hold:${String(name)}`), scope_kind: "tax_year", client_id: stableId(`client:${String(name)}`),
      tax_year: year, engagement_id: null, work_item_id: null, reason_code: reason, status: "active",
      placed_by: by, placed_at: `${String(since)}T10:00:00-05:00`, objects_held: 12, objects_applied: 12,
      released_at: null, released_by: null,
    })), // prettier-ignore
  };
}

export const BATCH_ID = stableId("destruction-batch:2026-Q3");
export function batch(state: Fil02State) {
  const destroyed = state === "i";
  return {
    batch_id: BATCH_ID, ref: "2026-Q3", scope_description: "Records past retention · Q3 2026",
    status: destroyed ? "destroyed" : "awaiting_approval", assembled_at: "2026-09-01T02:00:00-05:00",
    eligible_count: 1204, held_excluded_count: state === "e" || destroyed ? 3 : 0,
    destroyed_count: destroyed ? 1201 : 0, client_count: 41, confirmation_phrase: "DESTROY 2026-Q3",
    certificate_ref: destroyed ? "DC-2026-Q3" : null, hold_recheck_at: null,
    approvals: [
      { approver: { user_id: stableId("user:grace-holloway"), name: "Grace Holloway" }, approver_role: "firm_admin", approved_at: "2026-09-11T15:02:00-05:00" },
      ...(destroyed ? [{ approver: { user_id: stableId("user:felix-andersen"), name: "Felix Andersen" }, approver_role: "security_admin", approved_at: "2026-09-14T09:38:00-05:00" }] : []),
    ],
    allowed_actions: state === "f" ? [] : ["destruction.approve"],
  }; // prettier-ignore
}

export function versions() {
  return {
    record_type: "signed_efile_authorization",
    service_line: null,
    items: [1, 2].map((n) => ({
      version_id: stableId(`policy-version:${String(n)}`), version_no: n, retention_years: n === 1 ? 6 : 7,
      legal_minimum_years: 3, policy_text: n === 2 ? "Signed e-file authorizations are kept 7 years from the return due date." : null,
      effective_from: n === 2 ? "2026-01-01" : null,
      created_by: { user_id: stableId("user:felix-andersen"), name: "Felix Andersen" },
      created_at: n === 1 ? "2025-01-10T10:00:00-06:00" : "2026-01-05T10:00:00-06:00",
    })), // prettier-ignore
  };
}

export const PERSONA: Readonly<Record<Fil02State, string>> = {
  a: "felix-andersen",
  b: "felix-andersen",
  c: "felix-andersen",
  d: "felix-andersen",
  e: "felix-andersen",
  f: "samuel-ito",
  g: "felix-andersen",
  h: "felix-andersen",
  i: "felix-andersen",
};
