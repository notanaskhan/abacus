import { amount as formatAmount } from "@abacus/ui";

// Amounts as the server sends them: exact decimal strings, never floats (ADR-050). Parsing and
// rounding (half away from zero, on a scaled bigint) are format.ts's (F-05-T10); these three
// helpers keep the trial balance and working-paper screens' calls (TASK-319, TASK-320) and their
// one local rule: zero prints as a number, not an em dash, in these ledger columns. Moving them to
// the plan's dash is a decision for those screens, not for this helper.

const WHOLE = /^[+-]?\d+$/;

/** Thousands separators; two decimals when the value has a fraction. Negatives in parentheses. */
export function groupDigits(value: string): string {
  return formatAmount(value, WHOLE.test(value.trim()) ? "whole" : "cents", { zero: "explicit" })
    .text;
}

/** Whole dollars, half away from zero, on the string (no float). */
export function wholeDollars(value: string): string {
  return formatAmount(value, "whole", { zero: "explicit" }).text;
}

/** An amount for a trial balance's display unit; "—" when there is none. */
export function amount(value: string | null | undefined, unit: string = "cents"): string {
  if (value == null) return "—";
  return unit === "whole_dollars" ? wholeDollars(value) : groupDigits(value);
}
