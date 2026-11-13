// TXP-07 · Review › Capital Accounts words (T-05-T55; handoff TXP-07 spec.md; docs/screens/TXP-07.md).
// Verbatim from the handoff; strings marked undesigned are T-05-T03's.

export const COPY = {
  views: "Capital accounts view",
  byPartner: "By partner",
  byMovement: "By movement",
  title: "Capital Accounts",
  openExcel: "Open in Excel",
  signOff: "Sign off…",
  reviewed: (initials: string) => `Reviewed · ${initials}`,
  signedChip: (initials: string) => `✓ ${initials}`,
  pager: (from: number, to: number, of: number) =>
    `${String(from)}–${String(to)} of ${String(of)}`,
  pagerNext: "Next partners",
  pagerPrev: "Previous partners",
  tally: "Capital account checks",
  computing: "Workbook agent is computing the schedule",
  pending: "Pending",
  columns: { tax: "Tax", b704: "704(b)", book: "Book (tax basis)" },
  movementColumns: {
    partner: "Partner",
    pct: "Interest %",
    beginning: "Beginning",
    contributions: "Contrib.",
    income: "Income",
    transfers: "Transfers",
    distributions: "Distrib.",
    ending: "Ending",
  },
  rows: {
    beginning: "Beginning capital",
    cash: "Cash contributions",
    allocated: "Allocated income (rental + interest)",
    taxExempt: "Tax-exempt income",
    nondeductible: "Nondeductible noncapital expense",
    transfers: "Transfers — §706(d) assignment",
    guaranteed: "Guaranteed payments (memo)",
    distributions: "Cash distributions",
    ending: "Ending capital",
    total: "Total",
  },
  groups: {
    contributions: "CONTRIBUTIONS",
    income: "CURRENT-YEAR INCOME / (LOSS)",
    other: "OTHER ADJUSTMENTS",
    distributions: "DISTRIBUTIONS",
    tieOut: "TIE-OUT TO SCHEDULE L",
  },
  tieOut: {
    m2: "M-2 ending",
    schL: "Schedule L line 21",
    difference: "Difference",
    openIssue: "Open the issue (TXP-10)",
  },
  cards: {
    foots: "Capital foots",
    m2: "M-2 ties",
    book: "Book ties",
    derives: "Item L derives",
    begin: "Begin total",
    contributions: "Contributions",
    income: "CY income",
    other: "Other increases",
    transfers: "Transfers",
    distributions: "Distributions",
    end: "End total",
  },
  derivation: {
    begin: "BEGIN TOTAL = Σ partners' beginning capital (05 column B)",
    contributions: "CONTRIBUTIONS = Σ cash contributions (05 column C)",
    income: "CY INCOME = Analysis of Net Income line 1",
    other: "OTHER INCREASES = Σ tax-exempt income on the tax basis (05 column G)",
    transfers: "TRANSFERS = Σ §706(d) assignments; a transfer between partners nets to 0",
    distributions: "DISTRIBUTIONS = Σ cash distributions (05 column D)",
    end: "END TOTAL = Σ partners' ending capital (05 column F)",
  },
  amberCell: (cell: string) =>
    `${cell} is blank on the tax basis: expected 06 Schedule K!C31 × share`,
  transfersCell: "Opens the Allocation Structure (TXP-06)",
  offLink: "Open the issue (TXP-10)",
  footer:
    "704(b) = book: no revaluations and no §704(c) property. Tax column omits tax-exempt income → see M-2.",
  footerFixed: "704(b) = book: no revaluations and no §704(c) property.",
  transferNote:
    "Transfer = 5/35 of Pell Street Ventures' 6/30 capital of 2,319,835 (including 1,085 of first-half tax-exempt interest, per Reg. §1.704-1(b)(2)(iv)(l)) = 331,405; the same in all three columns.",
  // SHL-12 b2: blocked while a tie-out is off.
  blocked: (n: number) =>
    `${String(n)} tie-out${n === 1 ? " is" : "s are"} off. Resolve it or sign off with a note.`,
  resolve: "Resolve",
  signWithNote: "Sign off with a note",
  noteLabel: "Note",
  cancel: "Cancel",
} as const;

// The handoff's pane suffixes: a partner whose interest changed in the year.
export const PANE_NOTE: Readonly<Record<string, string>> = {
  "Pell Street Ventures LLC": "35% → 30%",
  "Pell Street II LLC": "from 7/1/2025",
};

export const GP_NAMES: ReadonlySet<string> = new Set(["Ridgeline GP LLC"]);
