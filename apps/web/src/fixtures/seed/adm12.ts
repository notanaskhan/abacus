// ADM-12 Monitoring & inspections (Q-05-T23; TASK-8933; handoff ADM-12 a–g; DEC-5935): Brightwater
// Hale's 2026 inspection cycle, Margaret Okonkwo (QM owner), Mon Sep 14, 2026, 9:24 AM CT. Every
// row is the handoff's; the footings are tests (adm12.foot.test.ts): 2 + 1 + 3 = 6 inspections,
// 1 + 1 + 0 + 1 = 3 findings from inspections, 5 open = 3 + 2 agent findings, and every inspector
// differs from the EP / signer (CM≠MO, TW≠CM, LK≠PR, TR≠VH, CM≠TW, IM≠NA).
import type {
  QualityAnnualEvaluationOut,
  QualityCandidateListOut,
  QualityFindingOut,
  QualityInspectionOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

const PEOPLE: Record<string, string> = {
  MO: "Margaret Okonkwo",
  CM: "Celia Marsh",
  TW: "Thomas Whitcombe",
  PR: "Priya Raman",
  LK: "Laura Kemp",
  VH: "Victor Hale",
  TR: "Tomas Reyes",
  NA: "Nadia Amari",
  IM: "Ivan Morales",
  HL: "Hannah Leclerc",
  SI: "Samuel Ito",
};
const person = (initials: string) => ({
  user_id: stableId(`user:${initials}`),
  name: PEOPLE[initials] ?? initials,
});

type Row = [
  string, string, string, QualityInspectionOut["kind"], string, string, string, string,
  QualityInspectionOut["status"], string | null, number, QualityInspectionOut["basis"],
]; // prettier-ignore
const ROWS: Row[] = [
  ["INS-26-01", "Meridian Tool & Die, Inc.", "FS audit FYE 12/31/2025", "post_issuance_archived", "MO", "CM", "Inventory significant risk; lender covenant reliance", "2026-08-31", "concluded", "2026-08-28", 1, "sqms1"],
  ["INS-26-02", "Bayside Electric Cooperative 401(k) Plan", "EBP PY2025", "pre_lock", "CM", "TW", "§103(a)(3)(C) audit; SOC 1 reliance", "2026-09-25", "in_progress", null, 1, "sqms1"],
  ["INS-26-03", "Juniper & Oak Interiors, LLC", "Preparation (AR-C 70) FY2025", "post_issuance_archived", "PR", "LK", "Non-attest service to a CAS client", "2026-07-31", "concluded", "2026-07-30", 0, "sqms1"],
  ["INS-26-04", "Cedar Hollow Farms, LLC", "Form 1065 TY2025", "post_filing", "VH", "TR", "Accepted 1065; reviewer judgment on checklist N/A answers", "2026-09-15", "concluded", "2026-09-09", 1, "firm_policy_c230_10_36"],
  ["INS-26-05", "Sterling Freight 401(k) Plan", "EBP PY2025", "in_process", "TW", "CM", "First cycle on BH Audit Methodology · EBP v3", "2026-10-30", "planned", null, 0, "sqms1"],
  ["INS-26-06", "Daniel & Ruth Okafor", "Form 1040 TY2025", "post_filing", "NA", "IM", "Schedule E rentals; random selection", "2026-11-20", "planned", null, 0, "firm_policy_c230_10_36"],
]; // prettier-ignore

/** The handoff's "Post-issuance (archived)" etc. differ from the kind word by row; kept here. */
export const KIND_WORDS: Record<string, string> = {
  "INS-26-01": "Post-issuance (archived)",
  "INS-26-02": "Pre-lock review (archive locks Sep 27)",
  "INS-26-03": "Post-issuance",
  "INS-26-04": "Post-filing",
  "INS-26-05": "In-process (pre-issuance)",
  "INS-26-06": "Post-filing",
};

export function inspections(cycle: 2026 | 2027 = 2026): QualityInspectionOut[] {
  if (cycle === 2027) return [];
  return ROWS.map(([ref, name, line, kind, ep, inspector, because, due, status, concluded, findings, basis]) => ({
    inspection_id: stableId(`inspection:${ref}`),
    ref,
    work_item_id: stableId(`work-item:${ref}`),
    engagement_name: name,
    engagement_line: line,
    kind,
    basis,
    signer: person(ep),
    inspector: person(inspector),
    selected_because: because,
    due_on: due,
    status,
    concluded_on: concluded,
    findings,
    allowed_actions: [],
  })); // prettier-ignore
}

export function candidates(): QualityCandidateListOut {
  return {
    rule_version: 2,
    items: [
      ["Sterling Freight 401(k) Plan", "0.82", "First cycle on BH Audit Methodology · EBP v3", ["TW"]],
      ["Harlow & Pike Holdings, Inc.", "0.74", "Group audit; component auditors", ["MO"]],
      ["Daniel & Ruth Okafor", "0.41", "Schedule E rentals; random selection", ["NA"]],
    ].map(([name, score, because, not]) => ({
      engagement_name: String(name),
      work_item_id: stableId(`candidate:${String(name)}`),
      risk_score: String(score),
      selected_because: String(because),
      not_objective_user_ids: (not as string[]).map((i) => stableId(`user:${i}`)),
    })), // prettier-ignore
  };
}

/** The objectivity lines the Select engagements sheet shows per inspector (b). */
export const OBJECTIVITY = [
  { inspector: "Celia Marsh", engagement: "Sterling Freight", objective: true },
  { inspector: "Thomas Whitcombe", engagement: "Sterling Freight", objective: false },
] as const;

type F = [
  string,
  string,
  string,
  string | null,
  string,
  string,
  QualityFindingOut["status"],
  string | null,
];
const FINDINGS: F[] = [
  ["QM-F-01", "Going-concern evaluation not documented before the report date", "inspection", "INS-26-01", "HL", "2026-10-31", "in_progress", "deficiency"],
  ["QM-F-02", "SOC 1 bridge letter not obtained for the uncovered Oct–Dec period", "inspection", "INS-26-02", "MO", "2026-09-30", "in_progress", "deficiency"],
  ["QM-F-03", "1065 checklist C-22 'Partnership representative designated' marked N/A without a reason", "inspection", "INS-26-04", "IM", "2026-10-15", "open", null],
  ["QM-F-04", "EBP Audit Workpapers override rate 9.0% (> 8%)", "agent_monitoring", null, "HL", "2026-10-15", "in_progress", null],
  ["QM-F-05", "K-1 Reconciliation Workpaper override rate 9.1% (> 8%)", "agent_monitoring", null, "SI", "2026-10-15", "open", null],
]; // prettier-ignore

const DETAIL: Record<string, Partial<QualityFindingOut>> = {
  "QM-F-02": {
    root_cause_category: "methodology",
    root_cause:
      "BH-EBP-140 step 8 (bridge letter and gap-period procedures, added in EBP v3) was published as guidance, not as a mandatory step, so the Bayside team did not perform it.",
    remediation:
      "Make BH-EBP-140 step 8 mandatory (KNW-03, EBP v3.1) and notify the 14 EBP engagements.",
    evaluated_by: "Margaret Okonkwo",
    evaluated_on: "2026-09-11",
  },
};

export function findings(): QualityFindingOut[] {
  return FINDINGS.map(([ref, title, source, insp, owner, due, status, evaluation]) => ({
    finding_id: stableId(`qm-finding:${ref}`),
    ref,
    title,
    source: source as QualityFindingOut["source"],
    agent_key: source === "agent_monitoring" ? (ref === "QM-F-04" ? "ebp_audit_workpapers" : "k1_reconciliation_workpaper") : null,
    inspection_ref: insp,
    status,
    evaluation,
    root_cause_category: null,
    owner: person(owner),
    due_on: due,
    raised_by_kind: source === "agent_monitoring" ? "system" : "human",
    version: 1,
    allowed_actions: ["edit", "evaluate", "remediate"],
    ...(DETAIL[ref] ?? {}),
  })) as QualityFindingOut[]; // prettier-ignore
}

export function evaluation(
  concluded: boolean,
  open = concluded ? 0 : 3,
): QualityAnnualEvaluationOut {
  return {
    year: 2026,
    status: concluded ? "concluded" : "not_started",
    responsible: person("MO"),
    decision_card_id: concluded ? stableId("decision-card:qm-2026") : null,
    concluded_at: concluded ? "2026-12-14T10:00:00-06:00" : null,
    checklist: {
      inspections_complete: false,
      remediation_significant: false,
      root_cause_reviewed: false,
      memo_drafted: false,
    },
    inspections_open: open,
    as_of: "2026-12-15",
    inputs_inspections: 6,
    inputs_findings: 5,
    inputs_objectives: 24,
    allowed_actions: concluded ? [] : ["conclude"],
  };
}

export const ADM12_CLOCKS = {
  a: "2026-09-14T09:24:00-05:00",
  b: "2026-09-14T09:24:00-05:00",
  c: "2026-09-14T09:24:00-05:00",
  d: "2026-12-14T09:24:00-06:00",
  e: "2026-09-14T09:24:00-05:00",
  f: "2026-12-14T10:05:00-06:00",
  g: "2026-09-14T09:24:00-05:00",
} as const;
export type Adm12State = keyof typeof ADM12_CLOCKS;
