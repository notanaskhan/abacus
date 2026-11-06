// AUD-20 (A-06-T30): Northwind's statements and checklist, verbatim from the handoff, in A-06-T19's
// shapes. Figures foot: 14,895,000 + 1,605,000 = 16,500,000; 312,400 + 48,600 = 361,000; 16,861,000;
// 13,940,000 + 288,500 = 14,228,500; 97 + 45 + 0 = 142; 63 = 24 + 15 + 24. Fictional. Dev and test.

import type {
  ChecklistOut,
  DisclosureItemOut,
  LineItemOut,
  StatementsOut,
} from "@abacus/api-client";

export const AUD20_ENGAGEMENT = "6f1c2a90-0000-4000-8000-000000000020";
export const AUD20_DOCUMENT = "6f1c2a90-0000-4000-8000-000000000a20";
const VERSION = "6f1c2a90-0000-4000-8000-000000000b20";
export type Aud20Variant = "a" | "b" | "c" | "e";

let serial = 0;
function uuid(): string {
  serial += 1;
  return `0a200000-0000-4000-8000-${serial.toString(16).padStart(12, "0")}`;
}

function line(
  statement: "net_assets" | "changes",
  section: string,
  key: string,
  label: string,
  current: string,
  prior?: string,
  options: { ties?: boolean; offBy?: string } = {},
): LineItemOut {
  const value = (year: number, amount: string) => ({
    id: uuid(),
    year,
    value: amount,
    source: "tb_linked" as const,
    citation_ids: [],
    ties: options.ties ?? true,
    off_by: options.offBy ?? null,
  });
  return {
    id: uuid(),
    statement_key: statement,
    section_key: section,
    line_key: key,
    label,
    position: 0,
    values:
      prior === undefined ? [value(2025, current)] : [value(2025, current), value(2024, prior)],
  };
}

const NET_ASSETS: LineItemOut[] = [
  line("net_assets", "investments", "krs_500", "KRS 500 Index Fund", "6120450.00", "5102300.00"),
  line("net_assets", "investments", "krs_2035", "KRS Target 2035 Fund", "2384910.00", "2011640.00"),
  line("net_assets", "investments", "krs_2045", "KRS Target 2045 Fund", "2915330.00", "2388970.00"),
  line("net_assets", "investments", "krs_bond", "KRS Bond Index Fund", "1408220.00", "1276090.00"),
  line("net_assets", "investments", "krs_intl", "KRS International Index Fund", "902610.00", "868000.00"),
  line("net_assets", "investments", "stable", "Harborline Stable Value Fund", "1163480.00", "1036000.00"),
  line("net_assets", "investments", "broker", "Self-directed brokerage accounts (BrokerWindow)", "1605000.00", "1257000.00"),
  line("net_assets", "total", "total_investments", "Total investments at fair value", "16500000.00", "13940000.00"),
  line("net_assets", "receivables", "notes", "Notes receivable from participants", "312400.00", "288500.00"),
  line("net_assets", "receivables", "contributions", "Employer and participant contributions", "48600.00", "0.00"),
  line("net_assets", "total", "total_receivables", "Total receivables", "361000.00", "288500.00"),
  line("net_assets", "grand", "net_assets", "Net assets available for benefits", "16861000.00", "14228500.00"),
]; // prettier-ignore

function changes(variant: Aud20Variant): LineItemOut[] {
  const off = variant === "b";
  const benefits = off
    ? line(
        "changes",
        "deductions",
        "benefits",
        "Benefits paid to participants",
        "797800.00",
        undefined,
        { ties: false, offBy: "14850.00" },
      )
    : line("changes", "deductions", "benefits", "Benefits paid to participants", "812650.00");
  return [
    line("changes", "additions", "appreciation", "Net appreciation in fair value of investments", "1755990.00"),
    line("changes", "additions", "dividends", "Interest and dividends", "342860.00"),
    line("changes", "additions", "total_investment", "Total investment income", "2098850.00"),
    line("changes", "additions", "loan_interest", "Interest income on notes receivable from participants", "17800.00"),
    line("changes", "additions", "participant", "Participant", "878400.00"),
    line("changes", "additions", "employer", "Employer", "392100.00"),
    line("changes", "additions", "rollover", "Rollover", "96400.00"),
    line("changes", "additions", "total_contributions", "Total contributions", "1366900.00"),
    line("changes", "total", "total_additions", "Total additions", "3483550.00"),
    benefits,
    ...(off ? [line("changes", "deductions", "deemed", "Deemed distributions of participant loans", "14850.00")] : []),
    line("changes", "deductions", "admin", "Administrative expenses", "38400.00"),
    line("changes", "total", "total_deductions", "Total deductions", "851050.00"),
    line("changes", "total", "net_increase", "Net increase", "2632500.00"),
    line("changes", "grand", "end_of_year", "End of year", "16861000.00"),
  ]; // prettier-ignore
}

export function statementsView(variant: Aud20Variant): StatementsOut {
  const allowed: StatementsOut["allowed_actions"] = ["statement.tie_out", "statement.send_draft", "disclosure_checklist.answer", "disclosure_checklist.review", "disclosure_checklist.export"]; // prettier-ignore
  const base = {
    statement_document_id: AUD20_DOCUMENT,
    framework_key: "asc_962",
    status: "draft" as const,
    allowed_actions: allowed,
  };
  if (variant === "c") return { ...base, management_approval: "none", current: null };
  const off = variant === "b";
  return {
    ...base,
    management_approval: variant === "e" ? "approved_by_management" : "none",
    current: {
      id: VERSION,
      version_no: off ? 1 : 3,
      source_snapshot_id: VERSION,
      drafted_by_kind: "system",
      out_of_date: false,
      content_hash: "0".repeat(64),
      created_at: "2026-10-02T15:00:00-05:00",
      lines: [...NET_ASSETS, ...changes(variant)],
      tie_out: {
        total: 63,
        tied: off ? 62 : 63,
        off: off ? [{ key: "benefits", amount: "14850.00", cause: "RJE-1" }] : [],
        engine_version: "1",
        inputs_hash: "0".repeat(64),
        ran_at: "2026-10-06T10:30:00-05:00",
      },
    },
  };
}

const NAMED: readonly DisclosureItemOut[] = (
  [
    ["plan_general", "Plan description (962-205-50)", "Is a general description of the plan agreement given (eligibility, contributions, vesting, loans, distributions)?", "yes", null, "Note 1"],
    ["plan_loans", "Plan description (962-205-50)", "Are participant loan terms disclosed (interest-rate range, maturities)?", "yes", null, "Note 5"],
    ["inv_hierarchy", "Investments (962-325 · 820)", "Is fair value shown by hierarchy level, with NAV-measured investments as a reconciling item?", "yes", null, "Note 3"],
    ["inv_contracts", "Investments (962-325 · 820)", "Are fully benefit-responsive investment contracts reported at contract value?", "na", "The Harborline Stable Value Fund is a CIT measured at NAV; the plan holds no direct contracts.", null],
    ["certified", "ERISA §103(a)(3)(C)", "Is the information certified by the qualified institution identified, with the certification's scope?", "yes", null, "Note 4"],
    ["party", "Parties in interest", "Are party-in-interest transactions disclosed (Harborline, Keystone fees paid by the plan)?", "yes", null, "Note 6"],
    ["delinquent", "Delinquent contributions", "Are late participant contributions and their correction disclosed?", "yes", null, "Note 9"],
    ["tax", "Tax status", "Is the plan's tax status and its reliance on the IRS opinion letter disclosed?", "yes", null, "Note 7"],
    ["form5500", "Form 5500", "Are differences between the FS and Form 5500 reconciled?", "yes", "Contributions receivable 48,600 — Summit prepares the 5500 on the cash basis (EBP-07)", "Note 8"],
    ["subsequent", "Subsequent events (855)", "Is the date through which subsequent events were evaluated disclosed?", "yes", "October 9, 2026", "Note 11"],
  ] as const
).map(([item_key, section, text, answer, reason, note_ref]) => ({
  item_key, section, text, answer, reason, note_ref, state: "reviewed", version: 1,
})); // prettier-ignore

export function checklistView(): ChecklistOut {
  // The other 132 rows are keyed placeholders under ADR-056, as A-06-T28's slice loads them.
  const yes = NAMED.filter((i) => i.answer === "yes").length;
  const na = NAMED.length - yes;
  const fill = (answer: "yes" | "na", n: number, from: number): DisclosureItemOut[] =>
    Array.from({ length: n }, (_, i) => ({
      item_key: `item_${String(from + i)}`,
      section: "Other disclosures",
      text: `Checklist item ${String(from + i)}`,
      answer,
      reason: answer === "na" ? "Not applicable to this plan." : null,
      note_ref: null,
      state: "reviewed",
      version: 1,
    }));
  const items = [...NAMED, ...fill("yes", 97 - yes, 11), ...fill("na", 45 - na, 108)];
  return { statement_document_id: AUD20_DOCUMENT, items, answered: 142, total: 142 };
}
