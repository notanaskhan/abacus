// KNW-04 j · Deadline rules (K-02-T17; DF-10, composed from the T12 grammar; one-day PF review): the
// read-only view over the platform reference sets. "Deadline rules" is the UI label FE-22 allows;
// code says due_date (DEC-14). Row values are the sets' own; these are the words around them.

export const DEADLINE_COPY = {
  label: "Deadline rules",
  helper:
    "Platform rules tables that Accrued applies to every firm: published by the platform under a two-person rule and read-only for every firm role. Firm overrides arrive later.",
  flagLabel: "Deadline rules",
  loading: "Loading the rules tables…",
  error: "The rules tables couldn't load.",
  retry: "Try again",
  version: (v: number): string => `v${String(v)}`,
  effective: (date: string): string => `Effective ${date}`,
  taxYear: (year: number): string => `TY${String(year)}`,
  source: (label: string): string => `Source: ${label}`,
  empty: "No postponements in effect.",
  columns: {
    form: "Form",
    period: "Year end",
    original: "Original due",
    extension: "Extension",
    authority: "Authority",
    date: "Date",
    name: "Holiday",
    jurisdiction: "Jurisdiction",
    notice: "Notice",
    areas: "Areas",
    window: "Window",
    postponedTo: "Postponed to",
    returnType: "Return",
    authorization: "Authorization form",
    revision: "Revision",
    threshold: "Threshold",
    transactions: "Transactions",
    serviceLine: "Service line",
    record: "Record",
    floor: "Minimum",
    anchor: "Counted",
  },
  fyeRule: {
    calendar_year: "Calendar year",
    fiscal_year: "Fiscal year",
    any: "Any year end",
  } as Record<string, string>,
  original: (months: number, day: number): string =>
    `${ordinal(day)} day of the ${ordinal(months + 1)} month`,
  extension: (form: string, months: number, day: number | null): string =>
    day === null
      ? `Form ${form} · ${String(months)} months`
      : `Form ${form} · ${String(months)} months, to the ${ordinal(day)}`,
  tolerances: "Pub 1345 tolerances",
  agi: "Total income or AGI",
  tax: "Tax, withholding, refund or balance due",
  years: (n: number): string => (n === 1 ? "1 year" : `${String(n)} years`),
  none: "—",
} as const;

/** 15 → "15th"; the month after the period end counts from 1 (3 months after → the 4th). */
function ordinal(n: number): string {
  const tens = n % 100;
  if (tens >= 11 && tens <= 13) return `${String(n)}th`;
  const suffix = ["th", "st", "nd", "rd"][n % 10] ?? "th";
  return `${String(n)}${n % 10 > 3 ? "th" : suffix}`;
}
