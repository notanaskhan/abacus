// TXT-02's words (T-07-T17), verbatim from the handoff (TXT-02 A–E, composed f1). Figures, labels
// of tree rows and the banner come from the read model (`GET …/fiduciary-computation`).
export const COPY = {
  header: "FAI → DNI → beneficiaries (tax year 2025)",
  signOff: "Sign off…",
  reapprove: "Re-approve…",
  openInExcel: "Open in Excel",
  calculation: "Calculation",
  byCharacter: "By character",
  changed: "Changed",
  reviewed: (initials: string) => `Reviewed · ${initials}`,
  waiting: "Approve the instrument interpretation to compute DNI.",
  error: "The calculation could not be loaded.",
  retry: "Retry",
  character: { interest: "Interest", ordinary_dividends: "Ordinary dividends", qualified_dividends: "of which qualified", total: "Total" },
  columns: { character: "Character", dni: "DNI" },
} as const;

/** Whole dollars with grouping, no "$"; negatives in parentheses (the calc-tree grammar). */
export function amountWords(value: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  const n = Number(value);
  const whole = Math.round(Math.abs(n)).toLocaleString("en-US");
  return n < 0 ? `(${whole})` : whole;
}
