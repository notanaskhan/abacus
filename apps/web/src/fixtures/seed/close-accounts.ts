// CLS-04 Close › Accounts (C-01-T37; handoff CLS-04): Copperleaf's August account tree, the Prepaid
// Insurance workpaper in each state and its register, verbatim from the handoff spec. The tree
// foots: assets 539,055.45 = liabilities 163,543.05 + equity 375,512.40. Accrued never posts: the
// approved state is read-only and the recorded state is the sync's (DV-1).
import type {
  AccountNodeOut,
  AccountTreeOut,
  CloseRegisterOut,
  CloseWorkpaperOut,
} from "@abacus/api-client";
import { closePerson } from "./close-book";
import { stableId } from "./prng";

/** Operating Checking ••4410's external id: the reconciliation CLS-05 opens (close-book). */
export const ACCOUNT_4410 = "35";
export const PREPAID = "prepaid-insurance";
/** Business Savings ••4436: its statement is still requested (CLS-05 g). */
export const ACCOUNT_4436 = "36";

type Kind = AccountNodeOut["classification"];

function leaf(
  classification: Kind,
  name: string,
  balance: string,
  extra: Partial<AccountNodeOut> = {},
): AccountNodeOut {
  const ref = extra.account_external_id ?? name.toLowerCase().replace(/[^a-z0-9]+/gu, "-");
  return {
    node_id: stableId(`close-account:${ref}`),
    kind: "account",
    classification,
    name,
    balance,
    account_external_id: ref,
    ...extra,
  };
}

function type_(
  classification: Kind,
  name: string,
  balance: string,
  children: AccountNodeOut[],
): AccountNodeOut {
  return {
    node_id: stableId(`close-type:${classification}:${name}`),
    kind: "account_type",
    classification,
    name,
    balance,
    children,
  };
}

function cls(classification: Kind, name: string, balance: string, children: AccountNodeOut[]) {
  return {
    node_id: stableId(`close-class:${classification}`),
    kind: "classification" as const,
    classification,
    name,
    balance,
    children,
  };
}

// C-02-T56: bpost (b for a non-attest W1 client: Post AJE), b2 (its confirm) and c (posted).
export type AccountsState = "a" | "a2" | "b" | "bpost" | "b2" | "c" | "cprime" | "d" | "e" | "f";

/** The tree (c′ after the sync read JE 48214: Prepaid 2,800.00, Other Current Asset 49,124.95). */
export function copperleafAccountTree(state: AccountsState = "a"): AccountTreeOut {
  const recorded = state === "cprime";
  const prepaidTally = recorded ? "recorded" : state === "d" ? "off" : "ties_once_posted";
  const A = "asset" as const;
  const L = "liability" as const;
  const E = "equity" as const;
  return {
    close_id: stableId("close:copperleaf:2026-08"),
    snapshot_id: stableId("snapshot:copperleaf:2026-08:2"),
    synced_at: recorded ? "2026-09-14T10:20:00-05:00" : "2026-09-14T09:00:00-05:00",
    totals: {
      asset: recorded ? "538355.45" : "539055.45",
      liability: "163543.05",
      equity: recorded ? "374812.40" : "375512.40",
    },
    nodes: [
      cls(A, "Asset", recorded ? "538355.45" : "539055.45", [
        type_(A, "Accounts Receivable", "18420.00", [leaf(A, "Accounts Receivable", "18420.00")]),
        type_(A, "Bank", "256610.50", [
          leaf(A, "Business Savings (Front Range Bank)", "60000.00", {
            mask: "4436",
            account_external_id: ACCOUNT_4436,
          }),
          leaf(A, "Operating Checking (Front Range Bank)", "184610.50", {
            mask: "4410",
            account_external_id: ACCOUNT_4410,
            tally: "reconciled",
          }),
          leaf(A, "Payroll Checking (Front Range Bank)", "12000.00", { mask: "4428" }),
        ]),
        type_(A, "Fixed Asset", "214200.00", [
          leaf(A, "Accumulated Depreciation", "-64200.00", { is_contra: true }),
          leaf(A, "Furniture & Fixtures", "25200.00"),
          leaf(A, "Leasehold Improvements", "97200.00"),
          leaf(A, "Roasting Equipment", "156000.00"),
        ]),
        type_(A, "Other Current Asset", recorded ? "49124.95" : "49824.95", [
          leaf(A, "Inventory", "42860.00"),
          leaf(A, "Prepaid Insurance", recorded ? "2800.00" : "3500.00", {
            account_external_id: PREPAID,
            tally: prepaidTally,
            ...(state === "d" ? { off_by: "60.00" } : {}),
          }),
          leaf(A, "Shopify Clearing", "1146.20"),
          leaf(A, "Square Clearing", "2318.75"),
          leaf(A, "Undeposited Funds", "0.00"),
        ]),
      ]),
      cls(L, "Liability", "163543.05", [
        type_(L, "Accounts Payable", "21380.45", [leaf(L, "Accounts Payable", "21380.45")]),
        type_(L, "Credit Card", "9846.12", [
          leaf(L, "Amex Business Card", "9846.12", { mask: "1009" }),
        ]),
        type_(L, "Long-Term Liability", "88500.00", [
          leaf(L, "Equipment Loan (Front Range Bank)", "88500.00"),
        ]),
        type_(L, "Other Current Liability", "43816.48", [
          leaf(L, "Accrued Expenses", "0.00"),
          leaf(L, "Accrued Payroll", "0.00"),
          leaf(L, "Deferred Revenue — Subscriptions", "31920.00"),
          leaf(L, "Payroll Liabilities", "4612.38"),
          leaf(L, "Sales Tax Payable", "7284.10"),
        ]),
      ]),
      cls(E, "Equity", recorded ? "374812.40" : "375512.40", [
        leaf(E, "Common Stock", "10000.00"),
        leaf(E, "Net Income", recorded ? "197020.00" : "197720.00"),
        leaf(E, "Retained Earnings", "263792.40"),
        leaf(E, "Shareholder Distributions", "-96000.00", { is_contra: true }),
      ]),
    ],
  };
}

const SCHEDULE = [
  ["2026-06", "4200.00"],
  ["2026-07", "3500.00"],
  ["2026-08", "2800.00"],
  ["2026-09", "2100.00"],
  ["2026-10", "1400.00"],
  ["2026-11", "700.00"],
] as const;

/** The Prepaid Insurance workpaper: a ties once posted, b approved (read-only), c′ recorded. */
export function copperleafPrepaidWorkpaper(state: AccountsState = "a"): CloseWorkpaperOut {
  const recorded = state === "cprime";
  const posted = state === "c";
  const approved = state === "b" || state === "bpost" || state === "b2";
  return {
    pending_entry_id: posted || recorded ? null : stableId("proposed-entry:aje-02"),
    pending_entry_status: posted || recorded ? null : approved ? "approved" : "within_threshold",
    pending_entry_version: 2,
    posting_open: state === "bpost" || state === "b2",
    posted_entry_number: posted ? "AJE-02" : null,
    posted_external_ref: posted ? "48214" : null,
    posted_at: posted ? "2026-09-14T10:20:00-05:00" : null,
    account_external_id: PREPAID,
    account_name: "Prepaid Insurance",
    gl_balance: recorded || posted ? "2800.00" : state === "d" ? "3560.00" : "3500.00",
    schedule_balance: "2800.00",
    tally: recorded ? "recorded" : posted ? "tie" : state === "d" ? "off" : "ties_once_posted",
    off_by: state === "d" ? "60.00" : null,
    review_issue_id: state === "d" ? stableId("close-issue:prepaid-off") : null,
    pending_entry_number: recorded || posted ? null : "AJE-02",
    approval: approved ? "Approved by RM under BH AJE thresholds v2 · 9:31 AM" : null,
    note: "Paid in full Jan 2, 2026 ($8,400). 7 months amortized through July = $4,900; GL $3,500 = $8,400 − $4,900.",
    recording: recorded
      ? {
          entry_number: "48214",
          external_txn_id: "48214",
          found_at: "2026-09-14T10:20:00-05:00",
          proposed_entry_id: stableId("proposed-entry:aje-02"),
          confirmed_by: closePerson("RM"),
        }
      : null,
    arrangements: [
      {
        arrangement_id: stableId("arrangement:cedar-mutual-bop-2026"),
        description: "Cedar Mutual business owner's policy 2026",
        expense_account_ref: "Insurance",
        kind: "prepaid",
        scheduled_total: "8400.00",
        frequency: "monthly",
        start_on: "2026-01-01",
        finish_on: "2026-12-31",
        source_citation_id: stableId("citation:cedar-mutual-declarations-p1"),
        version: 1,
      },
    ],
    lines: SCHEDULE.map(([period, ending]) => ({
      period,
      inflows: "0.00",
      aje: "-700.00",
      ending_balance: ending,
    })),
  };
}

/** e: the register (Detail), Jan 2 premium then seven monthly amortizations through Jul 31. */
export function copperleafPrepaidRegister(): CloseRegisterOut {
  const months = ["01-31", "02-28", "03-31", "04-30", "05-31", "06-30", "07-31"];
  return {
    account_external_id: PREPAID,
    next_cursor: null,
    items: [
      {
        line_ref: "bill-payment-2026-01-02",
        txn_date: "2026-01-02",
        txn_type: "Bill Payment",
        category: "Prepaid Insurance",
        payee: "Cedar Mutual Insurance Co.",
        memo: "BOP 2026 annual premium",
        amount: "8400.00",
      },
      ...months.map((d) => ({
        line_ref: `journal-entry-2026-${d}`,
        txn_date: `2026-${d}`,
        txn_type: "Journal Entry",
        category: "Insurance",
        payee: null,
        memo: "Monthly amortization",
        amount: "-700.00",
      })),
    ],
  };
}
