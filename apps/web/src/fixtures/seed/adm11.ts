// ADM-11 fixture data (Q-05-T19, TASK-8825; handoff ADM-11 spec + R2 revision): Margaret Okonkwo
// at Mon Sep 14, 2026 9:24 AM CT. Figures verbatim from the handoff; the backend computes them
// live (DEC-96): 206 of 3,410 overrides, 6.0%, tolerance 8%, 96.8% accuracy.
import { stableId } from "./prng";

export type Adm11State = "a" | "b" | "c" | "d" | "e";
const COMPONENTS = [
  ["governance_leadership", "Governance & leadership", 3, 4, 6, "ok", "MO"],
  ["ethical_requirements", "Relevant ethical requirements", 3, 6, 9, "at_risk", "TW"],
  ["acceptance_continuance", "Acceptance & continuance", 3, 5, 7, "ok", "MO"],
  ["engagement_performance", "Engagement performance", 7, 12, 19, "ok", "CM"],
  ["resources", "Resources (human, technological, intellectual)", 5, 7, 11, "at_risk", "MO"],
  ["information_communication", "Information & communication", 3, 4, 6, "ok", "PR"],
] as const;
export const NOTES: Readonly<Record<string, string>> = {
  ethical_requirements:
    "1 engagement independence confirmation missing: Ana Cruz · Northwind 401(k) — her sign-offs are blocked (CLI-08).",
  resources: "Technological resources: 2 agents above the 8% override tolerance.",
};
export const LABELS: Readonly<Record<string, string>> = Object.fromEntries(
  COMPONENTS.map(([k, l]) => [k, l]),
);
export const OWNERS: Readonly<Record<string, string>> = Object.fromEntries(
  COMPONENTS.map(([k, , , , , , o]) => [k, o]),
);

export function dashboard(state: Adm11State) {
  const denver = state === "b";
  const early = state === "d";
  return {
    cycle_year: 2026,
    office_id: denver ? stableId("office:denver") : null,
    objectives_firm_wide: true,
    tiles: {
      objectives_at_risk: 2,
      objectives: 24,
      findings_open: early ? 0 : denver ? 3 : 5,
      override_rate: denver ? "5.4" : "6.0",
      overrides: denver ? 61 : 206,
      outputs: denver ? 1128 : 3410,
      tolerance_pct: "8",
      accuracy: early ? null : "96.8",
      consultations_open: 2,
      days_to_evaluation: early ? 316 : 92,
    },
    components: COMPONENTS.map(([component, , , , , health]) => ({
      component, health, signals: NOTES[component] ? [NOTES[component]] : [],
    })), // prettier-ignore
    allowed_actions: state === "e" ? [] : ["quality.manage"],
  };
}

export function register() {
  return {
    objectives: COMPONENTS.map(([component, , objectives, risks, responses, health, owner], n) => ({
      objective_id: stableId(`qm-objective:${component}`),
      component,
      ref: `QO-${String(n + 1).padStart(2, "0")}`,
      title: LABELS[component] ?? component,
      owner: { user_id: stableId(`user:${owner}`), name: owner },
      health_flag: health === "at_risk" ? "at_risk" : null,
      risks,
      responses,
      version: 1,
      objectives,
    })),
    risks: 38,
    responses: 58,
  };
}

const AGENTS = [
  ["ebp_audit_workpapers", "EBP Audit Workpapers", 412, 37, "9.0", true, "QM-F-04"],
  ["k1_reconciliation_workpaper", "K-1 Reconciliation Workpaper", 318, 29, "9.1", true, "QM-F-05"],
  ["missing_document_chaser", "Missing Document Chaser", 880, 61, "6.9", false, null],
  ["return_review_packet", "Return Review Packet", 1260, 63, "5.0", false, null],
  ["bank_reconciliation", "Bank Reconciliation", 540, 16, "3.0", false, null],
] as const;

export function overrides() {
  return {
    window_days: 30,
    tolerance_pct: "8",
    sample_n: 25,
    outputs: 3410,
    overrides: 206,
    rate: "6.0",
    unrated: 9,
    rows: AGENTS.map(([agent_key, label, outputs, overrides, rate, above, finding_ref]) => ({
      agent_key, label, outputs, overrides, rate, above_tolerance: above, finding_ref, rated: true,
    })), // prettier-ignore
  };
}

export function reasons() {
  return {
    agent_key: "ebp_audit_workpapers",
    items: [
      { reason_code: "census_misread", count: 21 },
      { reason_code: "loan_offset", count: 9 },
      { reason_code: "other", count: 7 },
    ],
  };
}

export function consultationsLog() {
  return {
    counts: { open: 2 },
    items: [
      ["C-01", "2026-09-09T10:00:00-05:00", "MO"],
      ["C-05", "2026-09-10T10:00:00-05:00", "CM"],
    ].map(([ref, created_at, ep]) => ({
      consultation_id: stableId(`consultation:${ref}`), ref, created_at, status: "open",
      engagement_id: stableId(`engagement:${ref}`), raised_by_name: ep,
      consulted_with_name: null, consulted_with_user_id: null,
    })), // prettier-ignore
  };
}

const FINDINGS = [
  ["QM-F-02", "SOC 1 bridge letter not obtained for Oct–Dec", "inspection", "INS-26-02 Bayside 401(k)", "MO", "2026-09-30"],
  ["QM-F-01", "Going-concern evaluation not documented before the report date", "inspection", "INS-26-01 Meridian", "HL", "2026-10-31"],
  ["QM-F-03", "Checklist item C-22 marked N/A without a reason", "inspection", "INS-26-04 Cedar Hollow Farms", "IM", "2026-10-15"],
  ["QM-F-04", "EBP Audit Workpapers override rate 9.0%", "agent_monitoring", null, "HL", "2026-10-15"],
  ["QM-F-05", "K-1 Reconciliation Workpaper override rate 9.1%", "agent_monitoring", null, "SI", "2026-10-15"],
] as const;

export function findings(state: Adm11State) {
  if (state === "d") return { items: [], next_cursor: null };
  return {
    items: FINDINGS.map(([ref, title, source, inspection_ref, owner, due_on]) => ({
      finding_id: stableId(`qm-finding:${ref}`), ref, title, source, inspection_ref,
      agent_key: source === "agent_monitoring" ? "ebp_audit_workpapers" : null,
      status: "open", evaluation: null, root_cause_category: null,
      owner: { user_id: stableId(`user:${owner}`), name: owner }, due_on,
      raised_by_kind: source === "agent_monitoring" ? "system" : "human", version: 1, allowed_actions: [],
    })), // prettier-ignore
    next_cursor: null,
  };
}

export const CLOCKS: Readonly<Record<Adm11State, string>> = {
  a: "2026-09-14T09:24:00-05:00",
  b: "2026-09-14T09:24:00-05:00",
  c: "2026-09-14T09:24:00-05:00",
  d: "2026-02-02T09:24:00-06:00",
  e: "2026-09-14T09:24:00-05:00",
};
