// CLS-05 Close › Reconciliation (C-01-T38; handoff CLS-05): Operating Checking ••4410's August
// reconciliation in each state, built on CLS-05 a (`copperleafReconciliation4410`, close-book), and
// Savings ••4436 with its statement still requested. Verbatim from the handoff spec: b is Run 1
// (Sep 2) before the refund matched, "off 380.00"; c AJE-06 proposed 10:05; d reconciled and signed
// 2:31 PM, AJE-06 recorded in QuickBooks (JE 48218, DV-2) and #2281 carried forward.
import type { CloseRegisterOut, CloseReconciliationOut } from "@abacus/api-client";
import { closePerson, copperleafReconciliation4410 } from "./close-book";
import { ACCOUNT_4436 } from "./close-accounts";
import { stableId } from "./prng";

export type ReconciliationState = "a" | "a2" | "a3" | "b" | "c" | "d" | "e" | "f" | "g";

export const AJE_06 = stableId("proposed-entry:aje-06");

/** The agent's draft of AJE-06 (a2): a proposal a person adopts with Propose. */
export const AJE_06_DRAFT = {
  entry: "Dr Operating Checking $380.00 / Cr Cost of Goods Sold — Dairy $380.00",
  reasoning:
    "The Aug 27 statement line ROCKY RIDGE DAIRY CO REFUND 380.00 has no matching entry in the books.",
  citation: "FrontRange_4410_Statement_2026-08.pdf · p. 2",
};

export function copperleafReconciliation(
  state: ReconciliationState = "a",
): CloseReconciliationOut {
  const a = copperleafReconciliation4410();
  if (state === "b") {
    return {
      ...a,
      version: 1,
      adjusted_book: "184610.50",
      difference: "380.00",
      tally: "off",
      items: a.items.filter((i) => i.side === "bank"),
    };
  }
  if (state === "c") {
    return {
      ...a,
      items: a.items.map((i) => (i.side === "book" ? { ...i, proposed_entry_id: AJE_06 } : i)),
    };
  }
  if (state === "d") {
    return {
      ...a,
      version: 3,
      book_balance: "184990.50",
      tally: "reconciled",
      items: a.items
        .filter((i) => i.side === "bank")
        .map((i) => (i.ref === "#2281" ? { ...i, resolution: "carry_forward" as const } : i)),
      statement_lines: a.statement_lines.map((l) => ({ ...l, matched: true })),
      signed_off_by: closePerson("RM"),
      sign_off_blockers: [],
    };
  }
  return a;
}

/** g: Business Savings ••4436, its August statement requested Sep 1 (an empty viewer). */
export function copperleafSavings4436(): CloseReconciliationOut {
  return {
    reconciliation_id: stableId("reconciliation:copperleaf:4436:2026-08"),
    version: 1,
    account_external_id: ACCOUNT_4436,
    account_name: "Business Savings (Front Range Bank) ••4436",
    period_end: "2026-08-31",
    statement_evidence_version_id: null,
    statement_requested_on: "2026-09-01",
    balance_per_bank: null,
    adjusted_bank: null,
    book_balance: "60000.00",
    adjusted_book: "60000.00",
    difference: null,
    tally: "pending",
    items: [],
    statement_lines: [],
    signed_off_by: null,
    sign_off_stale: false,
    sign_off_blockers: ["statement_missing"],
    engine_version: "reconciliation-1.0.0",
    inputs_hash: "0".repeat(64),
  };
}

/** f: the August register beside the statement (the book side of page 2's lines and the two
 * outstanding checks, as the statement and the aging block carry them). */
export function copperleafRegister4410(): CloseRegisterOut {
  const line = (
    ref: string,
    date: string,
    type: string,
    payee: string | null,
    memo: string,
    amount: string,
  ) => ({
    line_ref: ref,
    txn_date: date,
    txn_type: type,
    category: null,
    payee,
    memo,
    amount,
  });
  return {
    account_external_id: "35",
    next_cursor: null,
    items: [
      line("dep-0824", "2026-08-24", "Deposit", null, "SQUARE INC TRANSFER", "2427.05"),
      line("dep-0825", "2026-08-25", "Deposit", null, "SQUARE INC TRANSFER", "7637.03"),
      line(
        "ach-0825",
        "2026-08-25",
        "Bill Payment",
        "Rocky Ridge Dairy Co.",
        "ROCKY RIDGE DAIRY ACH PMT",
        "-2860.00",
      ),
      line("dep-0826", "2026-08-26", "Deposit", null, "SQUARE INC TRANSFER", "2058.31"),
      line("chk-2287", "2026-08-26", "Check", "Denver Paper Supply", "#2287", "-3615.75"),
      line("dep-0827", "2026-08-27", "Deposit", null, "SQUARE INC TRANSFER", "2046.59"),
      line("dep-0828", "2026-08-28", "Deposit", null, "SQUARE INC TRANSFER", "2131.10"),
      line("chk-2290", "2026-08-28", "Check", "Mile High Window Cleaning", "#2290", "-802.33"),
      line("dep-0831", "2026-08-31", "Deposit", null, "SQUARE INC TRANSFER", "2356.11"),
      line("xfer-0831", "2026-08-31", "Transfer", null, "TRANSFER TO ••4428 PAYROLL", "-24600.00"),
    ],
  };
}
