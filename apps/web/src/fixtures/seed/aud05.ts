// AUD-05 Narrative workpaper, Risk Assessment (A-04-T21): the A-04-T04 record and the A-04-T19
// fraud session for Northwind PY2025, the words verbatim from the handoff spec. Dev and test only.

import type { FraudSessionOut, WorkpaperCellOut, WorkpaperRecordOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type Aud05Variant = "a" | "d" | "e";
export const RISK_PAPER = stableId("workpaper:northwind:risk_assessment");
// BH-EBP-110 step 9, the fraud discussion the minutes record.
const STEP_9 = "BH-EBP-110.9";
export const PBC_FLAG = stableId("flag:northwind:risk_assessment:reporting");

// (section, row, text, citations)
const ROWS: readonly (readonly [string | null, string, string, number])[] = [
  [
    null,
    "period",
    "Year ended December 31, 2025 · Employee benefit plan audit (ERISA §103(a)(3)(C))",
    0,
  ],
  [
    null,
    "purpose",
    "To understand the plan and its environment, and to identify and assess the risks of material misstatement at the financial statement and assertion levels.",
    0,
  ],
  [
    "menu_1",
    "procedures",
    "Read the plan document (2021 Cycle 3 restatement, signed Jun 15, 2021), the 2024 adoption agreement amendment, the 2025 SPD, the Harborline summary of net trust assets, the Keystone account balance and loan reports, and the Keystone SOC 1 Type 2 report.",
    3,
  ],
  [
    "menu_1",
    "governance",
    "Northwind Robotics 401(k) Plan (PN 001; Keystone plan ID 58217) is a single-employer, participant-directed defined contribution plan with a QACA safe-harbor design. The benefits committee oversees the plan; Dana Kowalski is the plan administrator.",
    2,
  ],
  [
    "menu_1",
    "framework",
    "ERISA Title I and the Internal Revenue Code. Large-plan Form 5500 with Schedule H (286 participants with balances at January 1, 2025). The plan administrator elected an ERISA §103(a)(3)(C) audit; Harborline Trust Company certifies the investment information.",
    1,
  ],
  [
    "menu_1",
    "service_organizations",
    "Keystone (recordkeeping), Harborline (trustee and custody) and PayGrid (payroll) are relevant. See General Audit Planning › Service Organizations.",
    1,
  ],
  ["menu_1", "reporting", "", 0],
  [
    "menu_1",
    "conclusion_1",
    "The plan, its environment and its internal control are understood well enough to assess risk.",
    0,
  ],
  [
    "menu_2",
    "procedures",
    "Considered the risks of material misstatement due to fraud at the financial statement level. The engagement team discussed them on Sep 10, 2026, led by Margaret Okonkwo (see Fraud Brainstorming).",
    1,
  ],
  [
    "menu_2",
    "management_override",
    "Identified as a significant fraud risk at the financial statement level; it cannot be rebutted. Responses: test journal entries and adjustments, review estimates for bias, evaluate significant unusual transactions.",
    0,
  ],
  [
    "menu_2",
    "revenue_recognition",
    "The presumption is retained for contributions: participant deferrals withheld through PayGrid and the employer safe-harbor match funded on each pay date.",
    1,
  ],
  [
    "menu_2",
    "investment_income",
    "Rebuttal proposed: investment income is certified by Harborline. Awaiting Margaret Okonkwo.",
    0,
  ],
  [
    "menu_2",
    "conclusion_2",
    "Two significant risks: management override of controls (financial statement level; a significant risk in every audit under AU-C 240) and, proposed for the engagement partner, completeness and cutoff of contributions (assertion level).",
    0,
  ],
]; // fmt: skip

function cell(
  [section, row, text, cites]: (typeof ROWS)[number],
  n: number,
  variant: Aud05Variant,
): WorkpaperCellOut {
  const drafted = variant === "e" && section === "menu_2";
  return {
    sheet_key: "main",
    cell_key: `B${String(n + 2)}`,
    row_key: row,
    col_key: "value",
    section_key: section,
    value: { t: "text", v: text },
    value_source: drafted ? "agent" : "human",
    value_state: drafted ? "suggested" : "human",
    citation_ids: Array.from({ length: cites }, (_, i) =>
      stableId(`citation:northwind:risk:${section ?? "head"}:${row}:${String(i)}`),
    ),
    suggestion_id: drafted ? stableId(`suggestion:northwind:risk:${row}`) : null,
    tickmarks: [],
    updated_version_no: 2,
  };
}

export function aud05Record(variant: Aud05Variant): WorkpaperRecordOut {
  return {
    id: RISK_PAPER,
    code: "AUD-05",
    title: "Risk Assessment",
    kind: "risk_assessment",
    audit_area: null,
    tab: "risk",
    version_no: 2,
    current_version_no: 2,
    content_hash: "2".repeat(64),
    program_step_keys: ["BH-EBP-110.9"],
    sections: [
      {
        key: "menu_1",
        title: "MENU 1 — UNDERSTANDING THE PLAN",
        band_kind: "menu",
        sheet_key: "main",
        state: "in_progress",
        waiting_on_request_ids: [],
      },
      {
        key: "menu_2",
        title: "MENU 2 — OVERALL RISKS AND FRAUD",
        band_kind: "menu",
        sheet_key: "main",
        state: "in_progress",
        waiting_on_request_ids: [],
      },
    ],
    cells: ROWS.map((r, n) => cell(r, n, variant)),
    flags: [
      {
        id: PBC_FLAG,
        kind: "pbc_gap",
        section_key: "menu_1",
        row_key: "reporting",
        state: "open",
        text: "the trust agreement and the IRS opinion letter have not been received (requested Sep 1, due Sep 18).",
        converted_to_id: null,
        converted_to_kind: null,
      },
    ],
    sign_offs:
      variant === "d"
        ? [
            { level: "L1", initials: "MD", signed_at: "2026-09-14T13:10:00-05:00", stale: false },
            { level: "L2", initials: "HL", signed_at: "2026-09-14T16:52:00-05:00", stale: false },
          ]
        : [],
    allowed_actions: ["workpaper.edit", "attention_flag.convert"],
  };
}

const person = (slug: string, name: string, initials: string) => ({
  user_id: stableId(`user:${slug}`),
  name,
  initials,
});

export function aud05Fraud(partner: boolean): FraudSessionOut {
  return {
    id: stableId("fraud-session:northwind"),
    held_at: "2026-09-10T10:00:00-05:00",
    medium: "video",
    led_by: person("margaret-okonkwo", "Margaret Okonkwo", "MO"),
    attendees: [
      person("margaret-okonkwo", "Margaret Okonkwo", "MO"),
      person("hannah-leclerc", "Hannah Leclerc", "HL"),
      person("marcus-delaney", "Marcus Delaney", "MD"),
      person("ana-cruz", "Ana Cruz", "AC"),
    ],
    excluded: [
      {
        user_id: stableId("user:thomas-whitcombe"),
        name: "Thomas Whitcombe",
        reason: "eqr",
      },
    ],
    discussion: [
      {
        step_key: STEP_9,
        summary:
          "How fraud could occur in contributions and benefit payments; management override is presumed.",
      },
    ],
    minutes_status: "awaiting_approval",
    minutes_text:
      "The team discussed how fraud could occur in contributions and benefit payments; management override is presumed; no team member raised an override not already in the register.",
    minutes_source: "human",
    minutes_hash: "3".repeat(64),
    approved_at: null,
    approved_by_name: null,
    row_version: 2,
    allowed_actions: partner
      ? ["fraud_minutes.approve", "fraud_session.edit"]
      : ["fraud_session.edit"],
  };
}
