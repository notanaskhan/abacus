// T-08-T08 (DEC-5607): consumer fixtures for the T-08 stubs (docs/contracts/{season-setup,
// filing-deadlines,tax-practice}.md; SPEC-710). Typed with the generated client and validated
// against the OpenAPI document; the ENG-07, HOME-03 and TAX-10 figures foot. The pytest half is
// backend/tests/contracts/t08_practice/.
import type {
  FilingDeadlineCalendarOut,
  SeasonManifestOut,
  TaxPracticeTwoYearOut,
} from "@abacus/api-client";
import { describe, expect, it } from "vitest";
import { validateResponse } from "../schema-check";

const id = (n: number): string => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;
const HASH = "a".repeat(64);

// ENG-07 a (AC-1): six cohorts by office and segment.
const COHORTS: [string, string, number, number, number][] = [
  ["Chicago", "individuals_trusts", 65, 68, 74],
  ["Chicago", "entities_exempt", 30, 30, 33],
  ["Denver", "individuals_trusts", 42, 45, 48],
  ["Denver", "entities_exempt", 19, 19, 21],
  ["New York", "individuals_trusts", 38, 42, 45],
  ["New York", "entities_exempt", 20, 20, 20],
];

const manifest: SeasonManifestOut = {
  manifest_id: id(1),
  season_id: id(2),
  tax_year: 2025,
  version: 1,
  status: "ready",
  inputs_hash: HASH,
  tally: {
    engagements: 214,
    returns: 224,
    binders: 241,
    created: 126,
    cohorts_approved: 4,
    cohorts: 6,
    exceptions: 3,
  },
  offices: [
    { office_id: id(10), office_name: "Chicago", returns: 98 },
    { office_id: id(11), office_name: "Denver", returns: 64 },
    { office_id: id(12), office_name: "New York", returns: 62 },
  ],
  cohorts: COHORTS.map(([office, segment, e, r, b], i) => ({
    cohort_id: id(20 + i),
    position: i + 1,
    office_id: id(10 + Math.floor(i / 2)),
    office_name: office,
    segment: segment as "individuals_trusts" | "entities_exempt",
    status: i < 4 ? "approved" : "draft",
    display: i < 4 ? "approved" : "review_required",
    engagements: e,
    returns: r,
    binders: b,
    letters: e,
    invitations: i === 4 ? 61 : 0,
    exceptions: i === 4 ? 3 : 0,
    rows_hash: HASH,
  })),
  planner_available: true,
};

const SEP15 = [...Array(8).fill("1065"), ...Array(3).fill("1120-S"), "1040-ES"];
const calendar: FilingDeadlineCalendarOut = {
  view: "month",
  window_from: "2026-08-30",
  window_to: "2026-10-03",
  today: "2026-09-14",
  firm_zone: "America/Chicago",
  items: SEP15.map((form, i) => ({
    filing_deadline_id: id(100 + i),
    source_kind: form === "1040-ES" ? "estimate_batch" : "tax_return",
    client_name: `Client ${i + 1}`,
    filing_label: form,
    due_on: "2026-09-15",
    original_due_on: form === "1040-ES" ? "2026-09-15" : "2026-03-16",
    stage_code: "in_review",
    stage_label: "In review",
    risk: "due_7",
    days_left: 1,
    risk_label: "1 day left",
    owners: [],
  })),
  days: [{ on: "2026-09-15", total: 12, shown: [id(100), id(101), id(102)] }],
  remaining: 12,
};

// TAX-10 a (AC-21): 8 lines flagged; 2b and 34 stay below the threshold.
const FLAGGED = ["3a", "3b", "sch_a_11", "16", "23", "24", "sch3_10", "33"];
const twoYear: TaxPracticeTwoYearOut = {
  tax_return_id: id(200),
  current_summary_id: "2025I:FeldJ:V3",
  filter: "all",
  threshold: {
    source: "checklist_parameter",
    source_label: "1040 Review Checklist v6",
    version_id: id(201),
    amount: "1000.00",
    percent: "10.0",
  },
  lines: [...FLAGGED, "2b", "34"].map((key, i) => ({
    line_key: key,
    label: key,
    current: "0.00",
    prior: "0.00",
    delta: "0.00",
    flagged: i < FLAGGED.length,
    state: i < FLAGGED.length ? (key === "sch_a_11" ? "proposed" : "accepted") : null,
    below_reason: i < FLAGGED.length ? null : "below $1,000",
    values_hash: HASH,
  })),
  agi: "598030.00",
  agi_delta_pct: "8.4",
  total_tax: "123223.00",
  total_tax_delta_pct: "11.2",
  refund: "253.00",
  prior_refund: "1174.00",
  over_threshold: 8,
  accepted: 7,
  explain_available: true,
};

describe("T-08 stub fixtures", () => {
  it("ENG-07 a: 214 · 224 · 241 foot across six cohorts", () => {
    const sum = (k: "engagements" | "returns" | "binders"): number =>
      manifest.cohorts.reduce((n, c) => n + c[k], 0);
    expect([sum("engagements"), sum("returns"), sum("binders")]).toEqual([214, 224, 241]);
    expect(manifest.offices.reduce((n, o) => n + o.returns, 0)).toBe(224);
    expect(
      validateResponse("GET", "/v1/seasons/{tax_year}/manifests/{manifest_id}", manifest),
    ).toEqual([]);
  });

  it("HOME-03 f: Sep 15 holds 12 = 8 × 1065 + 3 × 1120-S + 1", () => {
    const sep15 = calendar.items.filter((i) => i.due_on === "2026-09-15");
    expect(sep15.length).toBe(12);
    expect(sep15.filter((i) => i.filing_label === "1065").length).toBe(8);
    expect(calendar.days?.[0]?.total).toBe(12);
    expect(validateResponse("GET", "/v1/filing-deadlines", calendar)).toEqual([]);
  });

  it("TAX-10 a: exactly 8 flagged lines, 7 of 8 accepted", () => {
    expect(twoYear.lines.filter((l) => l.flagged).length).toBe(twoYear.over_threshold);
    expect(twoYear.lines.filter((l) => l.state === "accepted").length).toBe(twoYear.accepted);
    expect(validateResponse("GET", "/v1/tax-returns/{return_id}/two-year", twoYear)).toEqual([]);
  });
});
