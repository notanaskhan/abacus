// CLS-01 copy, verbatim from the handoff (CLS-01-closes-index-portfolio.md and its revision) and
// docs/screens/CLS-01.md. Status words come from the registry (C2), never from here.

export const COPY = {
  title: "Closes",
  noun: "closes",
  search: "Search closes",
  newClose: "New close…", // it opens ENG-03 with "Monthly close" preselected (a dialog opener)
  tracker: "1099 / W-9 tracker",
  chips: {
    period: "Period",
    status: "Status",
    preparer: "Preparer",
    reviewer: "Reviewer",
    attest: "Attest",
    all: "All",
    anyone: "Anyone",
    any: "Any",
    attestOnly: "Attest clients",
    pastDue: "Past due",
  },
  periods: {
    "2026-06": "June 2026",
    "2026-07": "July 2026",
    "2026-08": "August 2026",
    "2026-09": "September 2026",
  },
  /** "22 closes · 51 open issues · 2 past due · 3 running" */
  summary: (closes: string, open: string, pastDue: string, running: string): string =>
    `${closes} closes · ${open} open issues · ${pastDue} past due · ${running} running`,
  columns: {
    client: "Client",
    period: "Period",
    status: "Status",
    reconciled: "Reconciled",
    openIssues: "Open issues",
    due: "Due",
    prepRev: "Prep / Rev",
    agent: "Agent",
  },
  /** "43% (9 / 21)"; a full close reads "100%" and an empty one "0%". */
  reconciled: (pct: number, done: number, total: number): string =>
    done === 0 || done === total
      ? `${String(pct)}%`
      : `${String(pct)}% (${String(done)} / ${String(total)})`,
  pastDue: (n: number): string => `${String(n)} ${n === 1 ? "day" : "days"} past due`,
  delivered: (day: string): string => `Delivered ${day}`,
  running: "Running closing agent",
  runningPill: (n: number): string =>
    `Running closing agent · ${String(n)} ${n === 1 ? "close" : "closes"}`,
  /** "Run 2 · 6 of 9 complete · started 9:06 AM" */
  runLine: (run: number, done: number, total: number, at: string): string =>
    `Run ${String(run)} · ${String(done)} of ${String(total)} complete · started ${at}`,
  menu: { label: "Close actions", open: "Open", startRun: "Start run", viewPlan: "View plan" },
  startConfirm: {
    title: "Start run",
    body: "Statements not received — start the run anyway?",
    cancel: "Cancel",
    confirm: "Start run",
  },
  view: { list: "List", board: "Board" },
  empty: {
    title: "No closes this period",
    body: "Closes are created from a Monthly close engagement.",
  },
  attestEmpty: {
    title: "No attest clients this period",
    body: "Closes for audit or review clients show an 'Attest' badge after the client name and hold every entry for client approval before posting.",
  },
  noMatch: (q: string): string => `No closes match "${q}"`,
} as const;
