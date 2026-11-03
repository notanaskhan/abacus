// AUD-15 Findings register (A-06-T18; the handoff spec, Northwind PY2025): the nine findings the
// register lists (1 significant deficiency, 2 deficiencies, 1 exception for resolution, 5
// misstatements), each finding's detail, F-01's severity decision card and the Dec 26 late
// remittance EBP-04 found. Words and figures are the handoff's. Dev and test only.

import type {
  DecisionCardOut,
  FindingDetailOut,
  FindingRowOut,
  LateRemittanceOut,
  ListPageFindingRowOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

const id = (key: string): string => stableId(`aud15:${key}`);

export const MARGARET = stableId("person:margaret-okonkwo");
export const F01_CARD = id("card:F-01");
export const LATE_DEC26 = id("late:2025-12-26");

/** The artboard each state opens in (a–g). */
export type Aud15Variant = "a" | "b" | "c" | "d" | "e" | "f" | "g";

const CREATED = "2026-09-24T15:10:00Z";
const AGENT = "Accrued Agent · run #4188";

function row(
  ref: string,
  over: Partial<FindingRowOut> & Pick<FindingRowOut, "title" | "kind">,
): FindingRowOut {
  return {
    id: id(`finding:${ref}`),
    ref,
    coso_component: null,
    created_at: CREATED,
    created_by_name: AGENT,
    deficiency_status: null,
    route: "under_evaluation",
    severity_proposed: null,
    severity_concluded: null,
    workpaper_ref: null,
    ...over,
  };
}

function rows(variant: Aud15Variant): FindingRowOut[] {
  const concluded = variant === "c" || variant === "d";
  return [
    row("F-01", {
      kind: "control_deficiency",
      title: "December 26, 2025 payroll deposited January 9, 2026 — 9 business days after payday",
      coso_component: "control_activities",
      deficiency_status: variant === "d" ? "communicated" : concluded ? "concluded" : "proposed",
      severity_proposed: "significant_deficiency",
      severity_concluded: concluded ? "significant_deficiency" : null,
      workpaper_ref: "EBP-04",
    }),
    row("F-02", {
      kind: "control_deficiency",
      title:
        "Keystone SOC 1 covers Oct 1, 2024 – Sep 30, 2025; Oct–Dec 2025 gap not monitored until the Sep 21, 2026 bridge letter",
      coso_component: "monitoring",
      deficiency_status: variant === "d" ? "communicated" : "concluded",
      severity_proposed: "deficiency",
      severity_concluded: "deficiency",
      created_by_name: "Hannah Leclerc",
    }),
    row("F-03", {
      kind: "control_deficiency",
      title: "Opt-out elections missing for 4 auto-enrolled participants with no deferrals",
      coso_component: "control_activities",
      deficiency_status: "proposed",
      severity_proposed: "deficiency",
      workpaper_ref: "EBP-03",
    }),
    row("F-04", {
      kind: "control_deficiency",
      title:
        "Evidence for 4 of 6 complementary user entity controls (Keystone SOC 1) not provided",
      deficiency_status: "exception_for_resolution",
      workpaper_ref: "AUD-10",
    }),
    row("F-05", {
      kind: "misstatement",
      route: "converted_to_misstatement",
      title: "Contributions receivable not recorded for the December 26, 2025 payroll — $48,600",
      workpaper_ref: "AJE-1",
    }),
    row("F-06", {
      kind: "misstatement",
      route: "converted_to_misstatement",
      title:
        "Loan offsets of 3 terminated participants ($14,850) presented as deemed distributions",
      workpaper_ref: "RJE-1",
    }),
    row("F-07", {
      kind: "misstatement",
      route: "converted_to_misstatement",
      title:
        "Safe-harbor match not computed on bonus pay; the plan's compensation definition includes bonuses",
      workpaper_ref: "PAJE-1",
    }),
    row("F-08", {
      kind: "misstatement",
      route: "converted_to_misstatement",
      title: "Q4 2025 recordkeeping, TPA and audit fees not accrued — auditor estimate $13,050",
      workpaper_ref: "PAJE-2",
    }),
    row("F-09", {
      kind: "misstatement",
      route: "converted_to_misstatement",
      title: "Rollover received Dec 31, 2025, recorded Jan 2, 2026 — $4,210",
    }),
  ];
}

export function aud15List(variant: Aud15Variant): ListPageFindingRowOut {
  const items = variant === "g" ? [] : rows(variant);
  return { items, total: items.length };
}

const WHY_F01 =
  "Participant deferrals of $33,540.00 and safe-harbor match of $15,060.00 from the Friday, December 26, 2025 payroll reached Harborline Trust Company on Friday, January 9, 2026 — 9 business days after payday. The other 25 biweekly remittances in 2025 arrived 2 business days after payday, so the deferrals were reasonably segregable by December 30. PayGrid's remittance file needs a second approver at Northwind, and nobody approved it during the holiday shutdown. That points to a design gap, not a one-off. The plan had 286 participants at the beginning of the plan year, so the small-plan 7-business-day safe harbor does not apply.";

const EVALUATION: Readonly<Record<string, Readonly<Record<string, string>>>> = {
  "F-01": {
    magnitude: "$48,600.00 (19.3% of overall materiality $252,200)",
    likelihood: "Reasonably possible — no backup approver",
    compensating_controls: "None — HR reviews remittances monthly, after the fact",
    prohibited_transaction:
      "Yes · deferrals $33,540.00 · lost earnings $64.38 · correction pending (VFCP Self-Correction Component)",
    agent_proposal: "Significant deficiency (the Engagement Partner concludes)",
  },
  "F-07": {
    sample_error: "2,140.00",
    sample_size: "25",
    per_item: "85.60",
    population: "412 census records",
    projected: "35,267 → 35,300",
    method: "Mean per item",
    fs_effect: "Contributions receivable +35,300 · Employer contributions +35,300",
    disposition: "Passed on SUM · PAJE-1",
  },
};

const ALLOWED_DEFICIENCY: FindingDetailOut["allowed_actions"] = [
  "finding.update",
  "finding.convert",
  "finding.request_decision",
  "finding.mark_not_applicable",
];
const ALLOWED_EXCEPTION: FindingDetailOut["allowed_actions"] = [
  "finding.update",
  "finding.convert",
  "finding.resolve",
  "finding.mark_not_applicable",
];

export function aud15Detail(variant: Aud15Variant, findingId: string): FindingDetailOut | null {
  const finding = rows(variant).find((f) => f.id === findingId);
  if (finding === undefined) return null;
  const open = finding.deficiency_status === "proposed";
  const exception = finding.deficiency_status === "exception_for_resolution";
  return {
    finding,
    issue_id: id(`issue:${finding.ref}`),
    why_surfaced: finding.ref === "F-01" ? WHY_F01 : null,
    evaluation: { ...(EVALUATION[finding.ref] ?? {}) },
    citation_ids: [],
    decision_card_id: finding.ref === "F-01" && variant !== "a" ? F01_CARD : null,
    allowed_actions: exception ? ALLOWED_EXCEPTION : open ? ALLOWED_DEFICIENCY : [],
  };
}

const DECIDED_AT = "2026-09-28T21:12:00Z";

/** F-01's severity card: reserved to Margaret Okonkwo; decided in c and d. */
export function aud15Card(variant: Aud15Variant, persona: string): DecisionCardOut {
  const decided = variant === "c" || variant === "d";
  const reserved = persona === "margaret-okonkwo";
  return {
    card: {
      id: F01_CARD,
      engagement_id: id("engagement:northwind"),
      work_item_id: null,
      kind: "deficiency_severity",
      version_no: decided ? 2 : 1,
      status: decided ? "decided" : "awaiting_role",
      reserved_role: "engagement_partner",
      reserved_user_id: MARGARET,
      reserved_user_name: "Margaret Okonkwo",
      requested_at: "2026-09-28T15:15:00Z",
      blocking_count: 0,
      superseded_by_version: null,
      allowed_actions: !decided && reserved ? ["decision.decide"] : [],
    },
    question: "What is the severity of the December 26 late remittance?",
    context: [],
    options: [
      { key: "deficiency", label: "Deficiency", detail: null, figures: {}, recommended: false },
      {
        key: "significant_deficiency",
        label: "Significant deficiency",
        detail: null,
        figures: {},
        recommended: true,
      },
      {
        key: "material_weakness",
        label: "Material weakness",
        detail: null,
        figures: {},
        recommended: false,
      },
    ],
    factors: [],
    recommendation: null,
    citation_ids: [],
    blocking_refs: [],
    history: [],
    note: null,
    decision: decided
      ? {
          id: id("decision:F-01"),
          option_key: "significant_deficiency",
          factors: [],
          rationale: "No backup approver; the late deposit is a design gap.",
          seen_card_version: 1,
          decided_by_user_id: MARGARET,
          decided_by_name: "Margaret Okonkwo",
          decided_at: DECIDED_AT,
        }
      : null,
  };
}

/** EBP-04's late remittance behind F-01 (A-05-T24): the Dec 26 payroll. */
export const DEC26: LateRemittanceOut = {
  id: LATE_DEC26,
  payroll_date: "2025-12-26",
  deposited_on: "2026-01-09",
  business_days: 9,
  calendar_days: 14,
  established_practice_days: 2,
  amount: "33540.00",
  lost_earnings: "64.38",
  status: "pending_vfcp_scc",
  form_5330: "exposure",
};
