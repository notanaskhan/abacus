// The platform reference sets KNW-04 j reads (K-02-T17; C21, ADR-205; DF-10): one published
// version of each kind as of E0, in the C21 shapes. Fixture data for the gallery and the screen
// tests only: production rows are loaded with the operator CLI under the two-person rule (K-02-T06,
// K-02-T20), never from here. Every source citation carries "— verify", as the epic's example does,
// until K-02-T20's CPA review signs the production sets off.
import type { ReferenceSetOut, ReferenceSetVersionOut } from "@abacus/api-client";
import { stableId } from "./prng";

type Payload = ReferenceSetVersionOut["payload"];

interface SetDef {
  key: string;
  kind: ReferenceSetOut["kind"];
  title: string;
  jurisdiction: string | null;
  description: string | null;
  effective_from: string;
  tax_year: number | null;
  source: string;
  payload: Payload;
}

const DEFS: readonly SetDef[] = [
  {
    key: "us.due_date_rules.ty2025",
    kind: "due_date_rules",
    title: "Federal due-date rules · TY2025",
    jurisdiction: "US",
    description: null,
    effective_from: "2025-01-01",
    tax_year: 2025,
    source: "IRS Publication 509 (2026) — verify",
    payload: {
      kind: "due_date_rules",
      rows: [
        {
          form: "1040",
          authority: "IRC §6072(a)",
          fye_rule: "calendar_year",
          original: { months_after_period_end: 3, day: 15 },
          extension: { form: "4868", months: 6, day: null },
        },
        {
          form: "1065",
          authority: "IRC §6072(b)",
          fye_rule: "calendar_year",
          original: { months_after_period_end: 2, day: 15 },
          extension: { form: "7004", months: 6, day: null },
        },
        {
          form: "1120-S",
          authority: "IRC §6072(b)",
          fye_rule: "calendar_year",
          original: { months_after_period_end: 2, day: 15 },
          extension: { form: "7004", months: 6, day: null },
        },
        {
          form: "1120",
          authority: "IRC §6072(a)",
          fye_rule: "calendar_year",
          original: { months_after_period_end: 3, day: 15 },
          extension: { form: "7004", months: 6, day: null },
        },
        {
          form: "1041",
          authority: "IRC §6072(a)",
          fye_rule: "calendar_year",
          original: { months_after_period_end: 3, day: 15 },
          extension: { form: "7004", months: 5, day: 30 },
        },
        {
          form: "990",
          authority: "IRC §6072(e)",
          fye_rule: "any",
          original: { months_after_period_end: 4, day: 15 },
          extension: { form: "8868", months: 6, day: null },
        },
      ],
    },
  },
  {
    key: "us.legal_holidays.2026",
    kind: "legal_holidays",
    title: "Federal and DC legal holidays · 2026",
    jurisdiction: "US",
    description: null,
    effective_from: "2026-01-01",
    tax_year: null,
    source: "IRC §7503; 5 U.S.C. §6103; D.C. Code §1-612.02 — verify",
    payload: {
      kind: "legal_holidays",
      rows: [
        { date: "2026-01-01", jurisdiction: "US", name: "New Year's Day" },
        { date: "2026-01-19", jurisdiction: "US", name: "Birthday of Martin Luther King, Jr." },
        { date: "2026-02-16", jurisdiction: "US", name: "Washington's Birthday" },
        { date: "2026-04-16", jurisdiction: "DC", name: "District of Columbia Emancipation Day" },
        { date: "2026-05-25", jurisdiction: "US", name: "Memorial Day" },
        { date: "2026-06-19", jurisdiction: "US", name: "Juneteenth National Independence Day" },
        { date: "2026-07-03", jurisdiction: "US", name: "Independence Day (observed)" },
        { date: "2026-09-07", jurisdiction: "US", name: "Labor Day" },
        { date: "2026-10-12", jurisdiction: "US", name: "Columbus Day" },
        { date: "2026-11-11", jurisdiction: "US", name: "Veterans Day" },
        { date: "2026-11-26", jurisdiction: "US", name: "Thanksgiving Day" },
        { date: "2026-12-25", jurisdiction: "US", name: "Christmas Day" },
      ],
    },
  },
  {
    key: "us.disaster_postponements.2026",
    kind: "disaster_postponements",
    title: "Disaster postponements · 2026",
    jurisdiction: "US",
    description: null,
    effective_from: "2026-01-01",
    tax_year: null,
    source: "IRS disaster relief notices (IRC §7508A) — verify",
    payload: { kind: "disaster_postponements", rows: [] },
  },
  {
    key: "us.form_8879_set.ty2025",
    kind: "form_8879_set",
    title: "Form 8879 set and Pub 1345 tolerances · TY2025",
    jurisdiction: "US",
    description: null,
    effective_from: "2025-01-01",
    tax_year: 2025,
    source: "IRS Publication 1345 (rev.) — verify",
    payload: {
      kind: "form_8879_set",
      rows: [
        {
          return_type: "1040",
          authorization_form: "8879",
          jurisdiction: "US",
          revision: "TY2025",
          tax_year: 2025,
        },
        {
          return_type: "1065",
          authorization_form: "8879-PE",
          jurisdiction: "US",
          revision: "TY2025",
          tax_year: 2025,
        },
        {
          return_type: "1120-S",
          authorization_form: "8879-S",
          jurisdiction: "US",
          revision: "TY2025",
          tax_year: 2025,
        },
        {
          return_type: "1120",
          authorization_form: "8879-C",
          jurisdiction: "US",
          revision: "TY2025",
          tax_year: 2025,
        },
        {
          return_type: "1041",
          authorization_form: "8879-F",
          jurisdiction: "US",
          revision: "TY2025",
          tax_year: 2025,
        },
      ],
      tolerances: { total_income_or_agi_usd: 50, tax_withholding_refund_balance_usd: 14 },
    },
  },
  {
    key: "us.information_return_thresholds.2025",
    kind: "information_return_thresholds",
    title: "Information-return thresholds · payments in 2025",
    jurisdiction: "US",
    description: null,
    effective_from: "2025-01-01",
    tax_year: 2025,
    source: "IRS General Instructions for Certain Information Returns (2025) — verify",
    payload: {
      kind: "information_return_thresholds",
      rows: [
        { form: "1099-NEC", payment_year: 2025, threshold_usd: 600, min_transactions: null },
        { form: "1099-MISC", payment_year: 2025, threshold_usd: 600, min_transactions: null },
        { form: "1099-INT", payment_year: 2025, threshold_usd: 10, min_transactions: null },
        { form: "1099-DIV", payment_year: 2025, threshold_usd: 10, min_transactions: null },
      ],
    },
  },
  {
    key: "us.retention_minimums.2025",
    kind: "retention_minimums",
    title: "Retention minimums",
    jurisdiction: "US",
    description: null,
    effective_from: "2025-01-01",
    tax_year: null,
    source: "IRC §6501(a); Treas. Reg. §31.6001-1(e)(2); AU-C 230 — verify",
    payload: {
      kind: "retention_minimums",
      rows: [
        {
          service_line: "Tax",
          record_type: "Returns and supporting workpapers",
          floor_years: 3,
          anchor: "from the filing date",
          authority: "IRC §6501(a)",
        },
        {
          service_line: "Tax",
          record_type: "Employment tax records",
          floor_years: 4,
          anchor: "from the date the tax is due or paid",
          authority: "Treas. Reg. §31.6001-1(e)(2)",
        },
        {
          service_line: "Audit",
          record_type: "Audit documentation",
          floor_years: 5,
          anchor: "from the report release date",
          authority: "AU-C 230",
        },
      ],
    },
  },
];

const PUBLISHED_AT = "2026-01-05T15:00:00Z";

export const REFERENCE_SETS: readonly ReferenceSetOut[] = DEFS.map((d) => ({
  key: d.key,
  kind: d.kind,
  title: d.title,
  jurisdiction: d.jurisdiction,
  description: d.description,
  content_owner: "Accrued",
  current_version: 1,
  current_effective_from: d.effective_from,
}));

export const REFERENCE_SET_VERSIONS: Readonly<Record<string, ReferenceSetVersionOut>> =
  Object.fromEntries(
    DEFS.map((d) => [
      d.key,
      {
        id: stableId(`reference-set-version:${d.key}:1`),
        set_key: d.key,
        version: 1,
        status: "published",
        tax_year: d.tax_year,
        effective_from: d.effective_from,
        payload: d.payload,
        payload_hash: `sha256:${stableId(`payload:${d.key}`).replace(/-/gu, "")}`,
        payload_schema_version: 1,
        source_citations: [{ label: d.source, url: null }],
        change_reason: "Initial load",
        drafted_by: "ayushkbhatia",
        approved_by: "notanaskhan",
        published_at: PUBLISHED_AT,
      } satisfies ReferenceSetVersionOut,
    ]),
  );
