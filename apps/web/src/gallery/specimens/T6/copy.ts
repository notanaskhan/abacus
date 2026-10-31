// T6 workbook template copy (F-06-T01): the board's chrome (screens/T6). Values, tally results
// and totals are server data, never copy (ADR-050). F-06-T18 adds the view and scroller names,
// the tally labels and the pane footnotes (canvas `#t6`, `t6tally`).

export const COPY = {
  views: { byPartner: "By partner", byMovement: "By movement", calculation: "Calculation" },
  viewsLabel: "Capital accounts view",
  scroller: "Partners",
  title: "Capital Accounts",
  openInExcel: "Open in Excel",
  download: "Download",
  signOff: "Sign off…",
  running: "Workbook agent is running",
  building: "Building",
  explain: "Explain…",
  tiesOncePosted: "Ties once posted",
  changedAfterSignOff: "Changed after sign-off",
  // F-06-T20: the sign-off chips' group name and each chip's accessible name.
  signOffs: "Sign-offs",
  openSignOff: (name: string, level: string): string => `${name}, ${level}: open sign-off`,
  pending: "Pending",
  tally: {
    beginning: "Beginning capital",
    ending: "Ending capital",
    capitalFoots: "Capital foots",
    m2Ties: "M-2 ties",
    schLEquity: "Sch. L equity",
    k1ItemL: "K-1 item L",
  },
  info: {
    beginning: "Equals the 2024 ending capital on the filed return",
    ending: "Beginning, plus contributions and income, less distributions",
  },
  footnote: {
    byPartner: "Tax basis · December 31, 2025",
    byMovement: "Tax basis · threshold 25,000 a line, 100,000 on capital totals",
  },
  tables: { byPartner: "Capital by partner", byMovement: "Capital by movement" },
} as const;
