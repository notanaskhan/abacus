// EBP-09 (A-05-T45): Northwind's expenses and compliance at Thu Sep 24, 2026, verbatim from the
// handoff spec, in T43's shapes. Figures foot: 24,600 + 7,800 + 6,000 = 38,400 = 2i(1) 6,000 +
// 2i(2) 32,400; 41,500 - 3,100 = 38,400; 1,200 + 2,650 - 3,100 = 750. 2025 limits only. All names
// fictional. Dev and test only.

import type {
  ComplianceTestOut,
  ExpenseRowOut,
  ExpensesOut,
  FiguresOut,
  QualificationFactOut,
} from "@abacus/api-client";

export const EBP09_WORK_ITEM = "6f1c2a90-0000-4000-8000-0000000000e9";
export type Ebp09Variant = "a" | "d";

function expense(
  key: string,
  description: string,
  provider: string,
  disclosure: string | null,
  invoiced: string,
  credits: string,
  paid: string,
  line: ExpenseRowOut["schedule_h_line"],
  citations: string[],
  exception = false,
): ExpenseRowOut {
  return {
    id: `0a090000-0000-4000-8000-0000000000${key}`, line_key: key, description,
    provider_name: provider, disclosure_text: disclosure, invoiced, credits, paid_from_plan: paid,
    schedule_h_line: line, citation_labels: citations, exception,
  }; // prettier-ignore
}

const ROWS: ExpenseRowOut[] = [
  expense("a1", "Recordkeeping", "Keystone Retirement Services", "$6,150 per quarter, flat (disclosure Nov 4, 2024)", "24600.00", "0.00", "24600.00", "2i(2)", ["Keystone fee schedule 2025"]),
  expense("a2", "TPA — compliance testing & Form 5500", "Summit Plan Administrators", "$7,800 per year (disclosure Jan 6, 2025)", "7800.00", "0.00", "7800.00", "2i(2)", ["Summit invoice 2025"]),
  expense("a3", "Audit fee, PY2024 audit", "Brightwater Hale LLP", "Engagement letter fee $9,100", "9100.00", "-3100.00", "6000.00", "2i(1)", ["Brightwater Hale invoice 2025-0412", "Keystone ERISA budget statement Q2 2025"]),
]; // prettier-ignore

const FLAGGED = expense("a4", "Participant notice mailing", "Summit Plan Administrators", null, "1200.00", "0.00", "1200.00", "2i(2)", [], true); // prettier-ignore

export function expensesView(variant: Ebp09Variant): ExpensesOut {
  return {
    rows: variant === "d" ? [...ROWS, FLAGGED] : ROWS,
    invoiced: "41500.00", credits: "-3100.00", paid_from_plan: "38400.00", line_2i1: "6000.00",
    line_2i2: "32400.00", line_2i3: "0.00", line_2i4: "0.00", invoices_tie: true,
    exceptions: variant === "d" ? 1 : 0, engine_version: "1", inputs_hash: "0".repeat(64),
  }; // prettier-ignore
}

export const BUDGET_ACCOUNT: FiguresOut = {
  title: "ERISA budget account",
  rows: [
    { key: "jan_1", label: "Jan 1", amount: "1200.00", note: null },
    { key: "credits", label: "credits", amount: "2650.00", note: null },
    { key: "applied", label: "applied", amount: "-3100.00", note: null },
  ],
  total: "750.00",
  allowed_actions: [],
};

function test(
  key: string,
  result: ComplianceTestOut["result"],
  limit: string | null,
): ComplianceTestOut {
  return {
    id: `0a090000-0000-4000-8000-0000000001${String(key.length).padStart(2, "0")}`.replace(/.{2}$/, key.slice(0, 2)),
    test_key: key, plan_year: 2025, limit, limit_ref: null, result, accepted: true,
  }; // prettier-ignore
}

export const COMPLIANCE: ComplianceTestOut[] = [
  test("adp_acp", "exempt", null),
  test("top_heavy", "exempt", null),
  test("402g", "pass", "23500.00"),
  test("415c", "pass", "70000.00"),
  test("401a17", "pass", "350000.00"),
  test("compensation", "pass", null),
  test("auto_enrollment", "exception", null),
  test("hardship", "pass", null),
  test("rmd", "pass", null),
];

function fact(
  key: string,
  value: string,
  result: QualificationFactOut["result"],
): QualificationFactOut {
  return {
    id: `0a090000-0000-4000-8000-0000000002${key.slice(0, 2).replace(/[^0-9a-f]/g, "0")}`,
    fact_key: key, value, result, accepted: true,
  }; // prettier-ignore
}

export const QUALIFICATION: QualificationFactOut[] = [
  fact("plan_document", "Keystone pre-approved DC plan", "consistent"),
  fact("opinion_letter", "Jun 30, 2020", "consistent"),
  fact("restatement", "adoption agreement signed Jun 15, 2021 (deadline Jul 31, 2022)", "consistent"),
  fact("amendment", "signed Dec 9, 2024", "consistent"),
  fact("operational_failures", "missed auto-enrollment (4) → EPCRS correction by Oct 15, 2026", "exception"),
  fact("tax_note", "relies on the opinion letter", "consistent"),
  fact("part_iv", "4a Yes 33,540 · 4e bond $500,000", "consistent"),
]; // prettier-ignore
