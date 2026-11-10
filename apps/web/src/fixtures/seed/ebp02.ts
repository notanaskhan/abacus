// EBP-02 Plan provisions review (A-05-T17): the A-05-T16 shape for Northwind PY2025, the twenty
// provisions verbatim from the handoff spec (rows B2–B21, references C2–C21). Dev and test only.

import type { PlanReviewOut, ProvisionOut, SignOffChipOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type Ebp02Variant = "a" | "b" | "b2" | "c" | "d" | "e";

const ROWS: readonly (readonly [string, string, string, string])[] = [
  ["plan_year", "Plan year", "Jan 1 – Dec 31", "AA §1.05"],
  ["minimum_age", "Minimum age", "21", "AA §2.01(a)"],
  ["service_requirement", "Service requirement", "3 months (elapsed time)", "AA §2.01(b)"],
  ["entry_dates", "Entry dates", "First of month following", "AA §2.02"],
  ["excluded_classes", "Excluded classes", "Union employees; nonresident aliens", "AA §2.03"],
  ["long_term_part_time", "Long-term part-time", "2 years with 500+ hours", "AA §2.04"],
  ["compensation", "Compensation", "W-2 wages + pre-tax deferrals; bonuses included", "AA §3.01"],
  ["auto_enrollment", "Auto-enrollment", "QACA (§401(k)(13))", "AA §4.01"],
  ["default_deferral_rate", "Default deferral rate", "6%", "AA §4.02"],
  [
    "auto_escalation",
    "Auto-escalation",
    "+1% each Jan 1 after one full plan year, to 15%",
    "AA §4.03",
  ],
  ["qdia", "QDIA", "KRS Target date fund nearest age 65", "AA §4.05"],
  ["roth_deferrals", "Roth deferrals", "Yes", "AA §4.06"],
  ["catch_up", "Catch-up", "Yes, incl. ages 60–63", "2024 Amend. §2"],
  ["safe_harbor_match", "Safe harbor match", "100% of first 1% + 50% of next 5%", "AA §5.01"],
  ["match_vesting", "Match vesting", "100% after 2 years of service", "AA §6.02"],
  ["forfeitures", "Forfeitures", "Reduce employer contributions", "AA §6.04"],
  ["loans", "Loans", "Up to 2 outstanding; $1,000 minimum; payroll repayment", "AA §7.01"],
  ["in_service_withdrawals", "In-service withdrawals", "Age 59½", "AA §8.01"],
  ["hardship", "Hardship", "Safe-harbor events; self-certification", "AA §8.02"],
  ["plan_expenses", "Plan expenses", "Reasonable expenses may be paid from plan", "AA §9.04"],
];
// The two rows the 2024 amendment governs: absent from Version 1 (b2).
const AMENDED = new Set(["long_term_part_time", "catch_up"]);
export const PAPER = stableId("workpaper:northwind:ebp_02");
export const SPD_2025 = stableId("evidence_version:northwind:spd_2025");
const HL: SignOffChipOut = {
  level: 1,
  initials: "HL",
  name: "Hannah Leclerc",
  at: "2026-09-14T09:40:00-05:00",
  stale: false,
};
const REVIEWED: SignOffChipOut = {
  ...HL,
  level: 2,
  at: "2026-09-17T15:10:00-05:00",
};

function row(
  [key, label, value, reference]: readonly [string, string, string, string],
  n: number,
  variant: Ebp02Variant,
): ProvisionOut {
  const verified = variant === "a" || variant === "e";
  return {
    key,
    label,
    value,
    reference,
    cell: `B${String(n + 2)}`,
    value_hash: `${"0".repeat(56)}${String(n).padStart(8, "0")}`,
    verified,
    conflict: variant === "c" && key === "entry_dates" ? "SPD: quarterly" : null,
    amended_on: variant === "d" && key === "catch_up" ? "2025-01-01" : null,
    conflict_source:
      variant === "c" && key === "entry_dates"
        ? {
            evidence_version_id: SPD_2025,
            note: "The SPD (2025, p. 6) says entry is on the first day of each calendar quarter.",
          }
        : null,
    citation_count: 1,
  };
}

export function ebp02Review(variant: Ebp02Variant): PlanReviewOut {
  const v1 = variant === "b2";
  const provisions = ROWS.map((r, n) => row(r, n, variant)).filter(
    (p) => !v1 || !AMENDED.has(p.key),
  );
  const verified = provisions.filter((p) => p.verified).length;
  const signOffs =
    variant === "a" ? [HL] : variant === "e" ? [HL, REVIEWED] : ([] as SignOffChipOut[]);
  return {
    version_no: v1 ? 1 : 2,
    verified,
    total: provisions.length,
    provisions,
    allowed_actions: v1 ? [] : ["field.sign_off"],
    workpaper_id: PAPER,
    sign_offs: signOffs,
    version_diff: v1
      ? {
          current_version_no: 2,
          added_labels: ROWS.filter(([key]) => AMENDED.has(key)).map(([, label]) => label),
        }
      : null,
  };
}
