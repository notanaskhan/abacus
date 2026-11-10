// EBP-03 Eligibility testing (A-05-T23; the handoff spec): Northwind PY2025's 25 sampled
// participants in A-03's order, census against PayGrid's HR record, with code's entry date and
// the result. Words and dates verbatim from the handoff; the date of birth is masked (A-05-T18,
// DEC-2225). Dev and test only.

import type { EligibilitySampleOut, EligibilitySampleRowOut } from "@abacus/api-client";
import { stableId } from "./prng";

export type Ebp03Variant = "a" | "b" | "c" | "d" | "e";
export const ELIGIBILITY_TEST = stableId("test:northwind:ebp_eligibility");

// (name, hire, entry, rate, result in a); hire and HR agree except row 22.
const ROWS: readonly (readonly [string, string, string, string, "pass" | "exception"])[] = [
  ["Alicia Brennan", "2025-02-10", "2025-06-01", "8% elected", "pass"],
  ["Tomás Ibarra", "2021-06-14", "2021-10-01", "10% elected", "pass"],
  ["Priyanka Desai", "2025-04-07", "2025-08-01", "6% default", "pass"],
  ["Gordon Whitfield", "2012-09-04", "2013-01-01", "15% elected", "pass"],
  ["Mei Tanaka", "2024-09-16", "2025-01-01", "6% default", "pass"],
  ["Darnell Hughes", "2023-03-06", "2023-07-01", "7% default", "pass"],
  ["Sofia Marchetti", "2025-06-02", "2025-10-01", "5% elected", "pass"],
  ["Kwame Mensah", "2025-03-17", "2025-07-01", "0% — no opt-out", "exception"],
  ["Rebecca Lindgren", "2019-10-21", "2020-02-01", "7% elected", "pass"],
  ["Hiroshi Nakamura", "2024-11-04", "2025-03-01", "6% elected", "pass"],
  ["Ingrid Solberg", "2017-02-13", "2017-06-01", "12% elected", "pass"],
  ["Felipe Navarro", "2023-08-28", "2023-12-01", "7% default", "pass"],
  ["Aisha Rahman", "2025-07-14", "2025-11-01", "6% default", "pass"],
  ["Connor Gallagher", "2015-05-11", "2015-09-01", "9% elected", "pass"],
  ["Yuki Mori", "2024-12-02", "2025-04-01", "0% — no opt-out", "exception"],
  ["Patrick Doyle", "2022-01-10", "2022-05-01", "10% elected", "pass"],
  ["Leila Farahani", "2024-07-08", "2024-11-01", "6% default", "pass"],
  ["Andre Wilkins", "2023-05-15", "2023-09-01", "0% opt-out on file (08/22/2023)", "pass"],
  ["Natalie Brooks", "2025-05-05", "2025-09-01", "6% default", "pass"],
  ["Vikram Sethi", "2018-08-06", "2018-12-01", "6% elected", "pass"],
  ["Chloe Dubois", "2016-11-14", "2017-03-01", "8% elected", "pass"],
  ["Benjamin Okoro", "2024-10-07", "2025-02-01", "6% default", "pass"],
  ["Teresa Romero", "2020-12-07", "2021-04-01", "4% elected", "pass"],
  ["Ethan Caldwell", "2022-06-27", "2022-10-01", "8% default", "pass"],
  [
    "Fatima Qureshi",
    "2025-02-03",
    "2025-09-01",
    "6% default (age 21 on 08/19/2025 governs)",
    "pass",
  ],
]; // fmt: skip

const MISSED: Readonly<Record<string, readonly [string, string]>> = {
  "Kwame Mensah": ["2472.00", "1442.00"],
  "Yuki Mori": ["3168.00", "1848.00"],
};

function result(
  variant: Ebp03Variant,
  position: number,
  base: "pass" | "exception",
): EligibilitySampleRowOut["result"] {
  if (variant === "b")
    return position <= 6 ? (base === "pass" ? "agent_tested" : base) : "not_started";
  if (position === 22) return variant === "c" ? "needs_human" : "no_effect";
  if (base === "exception") return "exception";
  return variant === "a" || variant === "c" ? "agent_tested" : "pass";
}

function row(
  variant: Ebp03Variant,
  [name, hire, entry, rate, base]: (typeof ROWS)[number],
  i: number,
): EligibilitySampleRowOut {
  const position = i + 1;
  const missed = MISSED[name];
  return {
    position,
    item_id: stableId(`sample:northwind:eligibility:${String(position)}`),
    participant_id: stableId(`participant:northwind:${name}`),
    record_key: `NW-${String(1183 + position)}`,
    census_name: name,
    hr_first_name: name.split(" ")[0] ?? null,
    dob_masked: "••/••/••••",
    census_hire: hire,
    hr_hire: position === 22 ? "2024-10-14" : hire,
    // Only where hire + 3 months governs: an age-21 date would disclose the date of birth.
    eligible_on: position === 1 ? "2025-05-10" : null,
    entry_on: entry,
    recordkeeper_entry_on: entry,
    rate_label: rate,
    result: result(variant, position, base),
    note: position === 22 ? "No effect: entry 02/01/2025 either way" : null,
    hr_record_version_id: stableId(`evidence:northwind:hr-record:${String(position)}`),
    missed_deferral: missed?.[0] ?? null,
    missed_match: missed?.[1] ?? null,
  };
}

export function ebp03Sample(variant: Ebp03Variant): EligibilitySampleOut {
  const rows = ROWS.map((r, i) => row(variant, r, i));
  return {
    test_id: ELIGIBILITY_TEST,
    version_no: variant === "d" || variant === "e" ? 2 : 1,
    rows,
    exceptions: rows.filter((r) => r.result === "exception").length,
    needs_human: rows.filter((r) => r.result === "needs_human").length,
    prepared_by: variant === "d" || variant === "e" ? "AC" : null,
    reviewed_by: variant === "e" ? "HL" : null,
    allowed_actions: ["test.mark", "pii.reveal", "field.sign_off", "finding.create"],
    workpaper_id: stableId("workpaper:northwind:ebp_eligibility"),
    entry_rule: { state: "verified", minimum_age: 21, service_months: 3 },
  };
}

/** f: EBP-02's entry rule is not verified yet, so code computed nothing (DEC-2482). */
export function ebp03Unverified(): EligibilitySampleOut {
  const sample = ebp03Sample("a");
  return {
    ...sample,
    entry_rule: { state: "unverified", minimum_age: null, service_months: null },
    rows: sample.rows.map((r) => ({
      ...r,
      eligible_on: null,
      entry_on: null,
      rate_label: r.rate_label.endsWith("default") ? "" : r.rate_label,
      note: null,
      missed_deferral: null,
      missed_match: null,
    })),
  };
}
