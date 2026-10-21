// SPEC-029 (TASK-057): what code found in an upload, in plain words. Every message is a fixed
// template (ADR-111): the only values in it are dates and amounts the server computed.
import type { CheckOut } from "@abacus/api-client";
import { longDate, usd } from "./importMessages";

const UNREADABLE: Record<string, string> = {
  scanned:
    "This looks like a scanned copy, so we can't read it. Please upload the statement you download from your bank's website.",
  encrypted:
    "This file is password-protected. Enter its password to unlock it, or upload a copy without a password.",
  damaged: "This file couldn't be opened. Please save it again and upload the new copy.",
  too_large: "This file is too large to read. Please upload a shorter export.",
  crashed: "This file couldn't be opened. Please save it again and upload the new copy.",
};

const KIND_NOUN: Record<string, string> = {
  bank_statement: "statement",
  ar_aging: "aging",
  ap_aging: "aging",
  schedule: "schedule",
};

function noun(check: CheckOut): string {
  return KIND_NOUN[check.document_kind ?? ""] ?? "file";
}

/** The message for a problem a client can fix (client audience), or null for none. */
export function problemMessage(check: CheckOut): string | null {
  if (check.outcome !== "problem") return null;
  const found = check.found_date;
  const expected = check.expected_date;
  switch (check.code) {
    case "unreadable":
      return UNREADABLE[check.reason ?? ""] ?? "We couldn't read this file.";
    case "duplicate":
      return "This file is already uploaded elsewhere in this audit.";
    case "stale_as_of":
    case "wrong_period":
      if (found == null || expected == null) {
        return `This ${noun(check)} isn't for the year end.`;
      }
      return check.document_kind === "bank_statement"
        ? `This statement ends on ${longDate(found)}; we need one that includes ${longDate(expected)}.`
        : `This ${noun(check)} is as of ${longDate(found)}; we need it as of ${longDate(expected)}.`;
    case "wrong_entity":
      return "This looks like it's for a different company.";
    case "totals_dont_add_up": {
      const off = check.difference != null ? ` (off by ${usd(check.difference)})` : "";
      return check.document_kind === "bank_statement"
        ? `The balances on this statement don't add up${off}. Please check it's the complete statement.`
        : `The totals in this ${noun(check)} don't add up${off}. Please check it and upload it again.`;
    }
    case "ledger_cross_check":
      return crossCheckMessage(check);
    // Firm only (SPEC-030 amendment): numeric signs of editing, found by code.
    case "running_balance_breaks":
      return `A running balance doesn't follow from the line before it (off by ${usd(check.difference ?? "0")}).`;
    case "closing_balance_differs":
      return `The closing balance is stated differently on different pages (off by ${usd(check.difference ?? "0")}).`;
    default:
      return "Something in this file needs a look.";
  }
}

/** The firm's words for a ledger cross-check (firm audience only). */
export function crossCheckMessage(check: CheckOut): string {
  if (check.outcome === "not_applicable") {
    return CROSS_CHECK_SKIPPED[check.reason ?? ""] ?? "Not compared with the trial balance.";
  }
  const account = check.account_code ?? "the account";
  const what = check.document_kind === "bank_statement" ? "Closing balance" : "Aging total";
  if (check.outcome === "passed") {
    return `${what} agrees with account ${account} in the trial balance.`;
  }
  const difference = Number(check.difference ?? "0");
  const side = difference > 0 ? "more" : "less";
  return `${what} is ${usd(check.difference ?? "0")} ${side} than account ${account} in the trial balance.`;
}

const CROSS_CHECK_SKIPPED: Record<string, string> = {
  no_trial_balance: "No trial balance for the year end yet, so not compared.",
  no_closing_balance: "The statement doesn't print a closing balance, so not compared.",
  account_unclear: "Couldn't tell which cash account this statement is for, so not compared.",
  no_cash_account: "No cash account found in the trial balance, so not compared.",
  no_grand_total: "The aging has no grand total code could read, so not compared.",
  no_control_account: "No control account found in the trial balance, so not compared.",
};

const CHECK_NAMES: Record<string, string> = {
  unreadable: "Readable",
  duplicate: "Not a duplicate",
  stale_as_of: "Not stale",
  wrong_period: "Right period",
  wrong_entity: "Right company",
  totals_dont_add_up: "Totals add up",
  ledger_cross_check: "Agrees with the trial balance",
  running_balance_breaks: "Running balances follow",
  closing_balance_differs: "One closing balance throughout",
};

export function checkName(code: string): string {
  return CHECK_NAMES[code] ?? code;
}

const NOT_CHECKED: Record<string, string> = {
  no_period: "no period printed",
  stale: "already stale",
  no_name: "no account holder printed",
  not_printed: "not every balance is printed",
  no_as_of: "no as-of date",
  no_table: "no aging table found",
  no_values: "cells without saved values",
  no_total_row: "no total row",
  not_extracted: "this kind of file isn't read",
  legacy_format: "older file format",
  needs_ocr: "no readable text yet (scanned pages wait for text recognition)",
  no_running_balance: "no running balance column",
  stated_once: "closing balance stated once",
};

export function notCheckedReason(reason: string | null | undefined): string {
  return NOT_CHECKED[reason ?? ""] ?? "not checked";
}
