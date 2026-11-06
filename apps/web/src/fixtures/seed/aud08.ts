// AUD-08 Risk assessment register (A-04-T20): the A-04-T13 shapes for Northwind PY2025, the ten
// risks verbatim from the handoff spec (a), R3's drawer (b, b2) and the EP-approved register (d).
// Dev and test only.

import type { LinkageOut, RegisterOut, RegisterRiskOut, RiskDrawerOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type Aud08Variant = "a" | "b2" | "d" | "f";
type Rating = "low" | "moderate" | "high";

// code, area, level, assertions, IR, RMM, significance, fraud, response target, unaddressed
const ROWS: readonly (readonly [
  string,
  string,
  RegisterRiskOut["level"],
  RegisterRiskOut["assertions"],
  Rating,
  RegisterRiskOut["significance"],
  RegisterRiskOut["fraud"],
  string | null,
])[] = [
  [
    "R1",
    "Management override of controls",
    "financial_statement",
    [],
    "high",
    "mandatory",
    "presumed",
    "je",
  ],
  [
    "R2",
    "Contributions — participant & employer",
    "assertion",
    ["occurrence", "accuracy"],
    "moderate",
    "none",
    "none",
    "ebp04",
  ],
  [
    "R3",
    "Contributions — remittance & cutoff",
    "assertion",
    ["completeness", "cutoff"],
    "high",
    "proposed",
    "presumed",
    "ebp04",
  ],
  [
    "R4",
    "Investments at fair value (certified)",
    "assertion",
    ["existence", "valuation"],
    "low",
    "none",
    "none",
    "ebp06",
  ],
  [
    "R5",
    "Investment income (certified)",
    "assertion",
    ["occurrence", "accuracy"],
    "low",
    "none",
    "rebuttal_proposed",
    "ebp06",
  ],
  [
    "R6",
    "Notes receivable from participants",
    "assertion",
    ["existence", "valuation"],
    "moderate",
    "none",
    "none",
    "ebp05",
  ],
  [
    "R7",
    "Benefit payments",
    "assertion",
    ["occurrence", "accuracy"],
    "moderate",
    "none",
    "none",
    "ebp05",
  ],
  [
    "R8",
    "Participant accounts — eligibility & deferral data",
    "assertion",
    ["completeness", "accuracy"],
    "high",
    "none",
    "none",
    null,
  ],
  ["R9", "Administrative expenses", "assertion", ["occurrence"], "low", "none", "none", "ebp09"],
  [
    "R10",
    "Disclosures — parties in interest, Schedule H line 4a",
    "assertion",
    ["presentation", "completeness"],
    "moderate",
    "none",
    "none",
    "pii",
  ],
]; // fmt: skip

// Each risk's response, as the register's Response column shows it (the spec's text).
const TARGETS: Record<string, string> = {
  R1: "BH-EBP-110 step 12 → Journal entries & adjustments",
  R2: "BH-EBP-410 steps 2–4 → EBP-04 Contributions",
  R3: "BH-EBP-410 step 6 → EBP-04 Remittance timeliness",
  R4: "BH-EBP-310 steps 1–3 → EBP-06 Investments & certification",
  R5: "BH-EBP-310 step 4 → EBP-06",
  R6: "BH-EBP-310 step 6 → EBP-05 Loans",
  R7: "BH-EBP-410 step 8 → EBP-05 Distributions",
  R9: "BH-EBP-410 step 9 → EBP-09",
  R10: "BH-EBP-110 step 14 → Parties in interest",
};

const MARGARET_ACTIONS: RegisterRiskOut["allowed_actions"] = ["decision.decide"];
const HANNAH_ACTIONS: RegisterRiskOut["allowed_actions"] = [
  "risk.edit",
  "risk.link",
  "risk.route_for_approval",
  "workpaper.draft",
];
export const R3_CARD = stableId("decision-card:northwind:significant_risk");

function risk(row: (typeof ROWS)[number], variant: Aud08Variant): RegisterRiskOut {
  const [code, area, level, assertions, ir, significance, fraud, target] = row;
  const approved = variant === "d";
  return {
    id: stableId(`risk:northwind:${code}`),
    code,
    area_key: code.toLowerCase(),
    area_label: area,
    level,
    assertions,
    inherent_risk: ir,
    control_risk: "max",
    rmm: ir,
    significance: approved && significance === "proposed" ? "approved" : significance,
    fraud: approved && fraud === "rebuttal_proposed" ? "rebuttal_approved" : fraud,
    presumption_kind: code === "R1" ? "management_override" : "none",
    inherent_factors:
      code === "R3"
        ? [
            { factor: "susceptibility_to_fraud", rating: "high" },
            { factor: "change", rating: "moderate" },
            { factor: "complexity", rating: "low" },
            { factor: "subjectivity", rating: "low" },
            { factor: "uncertainty", rating: "low" },
          ]
        : [],
    unaddressed: target === null,
    status: approved ? "ep_approved" : "draft",
    version_no: 2,
    content_hash: "0".repeat(64),
    rmm_policy_version_id: null,
    allowed_actions: variant === "b2" ? MARGARET_ACTIONS : HANNAH_ACTIONS,
  };
}

export function aud08Register(variant: Aud08Variant): RegisterOut {
  const risks = ROWS.map((r) => risk(r, variant));
  const approved = variant === "d";
  return {
    risks,
    tally: {
      risks: 10,
      significant: 2,
      significant_proposed: approved ? 0 : 1,
      fraud: 2,
      high_rmm: 3,
      unaddressed: 1,
      ep_approval: approved ? "approved" : "pending",
    },
    register_hash: "1".repeat(64),
    approved_card_id: variant === "d" ? null : R3_CARD,
    allowed_actions: variant === "b2" ? MARGARET_ACTIONS : HANNAH_ACTIONS,
  };
}

export function aud08Linkage(): LinkageOut {
  return {
    risk_codes: ROWS.map((r) => r[0]),
    targets: Object.entries(TARGETS).map(([ref, label]) => ({
      kind: "workpaper",
      ref,
      label,
      registered: false,
    })),
    cells: ROWS.flatMap(([code, , , , , , , target]) =>
      target === null ? [] : [{ risk_code: code, target_ref: code, state: "linked" as const }],
    ),
  };
}

// A-04-T26 (f): R8 "Participant accounts — eligibility & deferral data", rationale drafted with the
// agent and not adopted (the R2 revision's words).
const R8_RATIONALE =
  "Deferral rates change each year under QACA escalation (6% default, +1% a year to 15%), and Internal Control lists 4 auto-enrolled participants whose opt-out elections are outstanding, so census and deferral data may be incomplete. RMM High.";

export function aud08Drawer(variant: Aud08Variant): RiskDrawerOut {
  if (variant === "f") {
    const r8 = risk(ROWS[7] as (typeof ROWS)[number], "a");
    return {
      risk: r8,
      rationale: R8_RATIONALE,
      rationale_suggestion_id: stableId("suggestion:northwind:R8:rationale"),
      citation_ids: [1, 2, 3].map((n) => stableId(`citation:northwind:R8:${String(n)}`)),
      versions: [],
      routed_to_name: null,
      routed_at: null,
      response_suggestion: {
        suggestion_id: stableId("suggestion:northwind:R8:response"),
        target_ref: "EBP-03",
        citations: 3,
        version: 1,
      },
    };
  }
  const r3 = risk(ROWS[2] as (typeof ROWS)[number], variant);
  return {
    risk: r3,
    rationale:
      "PayGrid withholds deferrals each biweekly pay date and Northwind uploads the deposit file to Keystone by hand. Internal Control row 2: the Dec 26, 2025 payroll ($48,600) was deposited on Jan 9, 2026, 9 business days later against Northwind's usual 2.",
    rationale_suggestion_id: null,
    citation_ids: [1, 2, 3, 4].map((n) => stableId(`citation:northwind:R3:${String(n)}`)),
    versions: [
      { version_no: 1, at: "2026-09-14T10:15:00-05:00", by_name: "Hannah Leclerc" },
      { version_no: 2, at: "2026-09-14T12:31:00-05:00", by_name: "Hannah Leclerc" },
    ],
    routed_to_name: "Margaret Okonkwo",
    routed_at: "2026-09-14T12:31:00-05:00",
  };
}
