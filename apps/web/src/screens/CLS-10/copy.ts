// CLS-10 Flux copy (C-01-T40): verbatim from the handoff's spec.md (CLS-10 a to e).
export const COPY = {
  segments: { issues: "Issues", adjustments: "Adjustments", flux: "Flux" },
  title: "Flux · {current} vs {prior}",
  threshold: "Threshold {label}",
  tally: {
    tested: "Lines tested",
    over: "Over threshold",
    explained: "Explained",
    unexplained: "Unexplained",
    accepted: "Accepted",
    acceptedValue: "{n} of {total}",
    pending: "Pending",
  },
  basis: { mom: "Month over month", yoy: "Year over year", budget: "Budget" },
  noBudget: "No budget on file",
  pane: "Income statement",
  openExcel: "Open in Excel",
  asAdjusted: "Amounts are as adjusted: posted and proposed entries included.",
  columns: {
    line: "Line",
    change: "Change",
    changePct: "Change %",
    test: "Test",
    explanation: "Explanation",
    status: "Status",
  },
  test: { within: "Within", over_both: "Over both", not_comparable: "Not comparable" },
  status: {
    within_threshold: "Within threshold",
    unexplained: "Unexplained",
    explained_draft: "Explained · draft",
    explained: "Explained",
    accepted: "Accepted · {initials}",
  },
  issue: "Issue",
  explain: "Explain…",
  accept: "Accept",
  explaining: "Accrued Agent is tracing the change…",
  banner: "{n} accepted explanations will appear in the {month} commentary (CLS-08)",
  bannerOne: "1 accepted explanation will appear in the {month} commentary (CLS-08)",
} as const;

export function fill(template: string, vars: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (_, k: string) => String(vars[k] ?? `{${k}}`));
}
