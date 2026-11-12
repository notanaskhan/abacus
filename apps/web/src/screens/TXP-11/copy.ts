// TXP-11 · Workpaper — Ridgeline workbook (T-05-T38; handoff TXP-11 spec.md; docs/screens/TXP-11.md).
// Verbatim from the handoff; the conflict line is undesigned (T-05-T03).

export const COPY = {
  grid: "Ridgeline workbook",
  openInExcel: "Open in Excel",
  version: "Version 2 · Run 2",
  readOnlyVersion: "Read-only: an earlier run",
  linkedIssue: "Linked issue · Tax-exempt interest 6,200 omitted…",
  citedBy: "Cited by 1 issue",
  evidence:
    "Evidence: 06 Schedule K!C31 · Municipal bond fund statement (Harborline, Dec 2025) p. 1",
  expectedH12: "='06 Schedule K'!C31 × 25% → 1,550",
  /** Undesigned (T-05-T03): the 409 path. */
  conflict: "This cell changed since you opened it. Reload to see the new value, then edit again.",
  reload: "Reload",
  saving: "Saving…",
} as const;

/** The workbook's sheets in tab order (the handoff's titles). */
export const SHEETS = [
  "01 Trial Balance",
  "02 Fixed Assets",
  "03 Liabilities",
  "04 Partner Txns",
  "05 Capital",
  "06 Schedule K",
  "07 M-2",
  "08 States",
  "09 K-1s",
] as const;
