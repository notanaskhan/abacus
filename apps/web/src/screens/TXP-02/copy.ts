// TXP-02 · Review › Financials (TB → TTB) words (T-05-T37; handoff TXP-02 spec.md; docs/screens/
// TXP-02.md). Verbatim from the handoff; the two undesigned strings are T-05-T03's.

export const COPY = {
  views: "Trial balance view",
  statements: "Statement",
  byAccount: "By Account",
  byLine: "Grouped by Form 1065 Line",
  full: "Full TB",
  balanceSheet: "Balance Sheet",
  incomeStatement: "Income Statement",
  openInExcel: "Open in Excel",
  journalEntry: "+ Journal entry…",
  table: "Ridgeline TB → TTB",
  tally: "Trial balance checks",
  building: "Workbook agent is importing the trial balance",
  pending: "Pending",
  map: "Map…",
  /** Undesigned (T-05-T03): the Unmapped card's filter link; the handoff makes the card itself
   * the control. */
  showUnmapped: "Show",
  exportBlocked: "1 unmapped account blocks export",
  footnote:
    "AJE-1 Dr Real estate taxes 18,500 / Cr Accrued expenses 18,500 (December installment) · TJE-1 reclass tax-exempt interest 6,200 to Schedule K line 18a (net 0) · PY = TY2024 pre-closing TB (2024 Form 1065 workbook)",
  columns: {
    code: "Acct #",
    name: "Account name",
    line: "Export",
    py: "PY",
    utb: "UTB",
    aje: "AJE",
    rje: "RJE",
    atb: "ATB",
    tje: "TJE",
    ttb: "TTB",
  },
  groups: {
    assets: "Assets",
    liabilities: "Liabilities",
    equity: "Equity",
    income: "Income",
    deductions: "Rental expenses (Form 8825)",
    unmapped: "Unmapped",
  },
  cards: {
    ttb: "TTB balanced",
    unmapped: "Unmapped",
    gross_rents: "Gross rents",
    total_deductions: "Total deductions",
    net_rental_income: "Net rental RE income",
    book_total_assets: "Book total assets",
  },
  info: {
    gross_rents: "Rents 3,776,500 + parking & other 96,400 = rental revenue 3,872,900",
    net_rental_income:
      "3,776,500 + 96,400 − 2,641,300 = 1,231,600 · Form 8825 → Schedule K line 2",
  },
} as const;
