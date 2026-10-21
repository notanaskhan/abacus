// Amounts as the server sends them: exact decimal strings, never floats (ADR-050). format.ts
// (F-05-T10) will own this.

/** Thousands separators and two decimals; negatives in parentheses. */
export function groupDigits(value: string): string {
  const [whole = "0", fraction] = value.replace(/^-/, "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  const decimals = fraction === undefined ? "" : `.${fraction.padEnd(2, "0").slice(0, 2)}`;
  return value.startsWith("-") ? `(${grouped}${decimals})` : `${grouped}${decimals}`;
}

/** Whole dollars, half away from zero, on the string (no float). */
export function wholeDollars(value: string): string {
  const negative = value.startsWith("-");
  const [whole = "0", fraction = ""] = value.replace(/^-/, "").split(".");
  const rounded = (fraction[0] ?? "0") >= "5" ? (BigInt(whole) + 1n).toString() : whole;
  const isZero = /^0+$/.test(rounded);
  return groupDigits(negative && !isZero ? `-${rounded}` : rounded);
}

/** An amount for a trial balance's display unit; "—" when there is none. */
export function amount(value: string | null | undefined, unit: string = "cents"): string {
  if (value == null) return "—";
  return unit === "whole_dollars" ? wholeDollars(value) : groupDigits(value);
}
