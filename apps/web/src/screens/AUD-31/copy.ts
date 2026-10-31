// AUD-31 · Trial balance mapping (A-03-T12): copy verbatim from the handoff's spec.md (states a–f)
// and docs/screens/AUD-31.md; strings marked (undesigned) are composed where nothing is drawn.

export const COPY = {
  title: "Trial balance mapping",
  cockpit: "Cockpit",
  focus: (entity: string, year: string): string => `${entity} · FY${year}`,
  sourceFile: "Source file",
  selectAccount: "Select an account to open its row in the source file.",
  sourceCaption: (confirmed: string | null): string =>
    confirmed === null
      ? "read-only ledger snapshot"
      : `read-only ledger snapshot · mapping confirmed ${confirmed}`,
  sourceColumns: ["Account", "Name", "Debit", "Credit"] as const,
  pills: {
    review: (n: number): string => `${String(n)} need review`,
    confirmed: (on: string): string => `Confirmed ${on}`,
    stale: "Changed after sign-off",
    inProgress: "In progress", // (undesigned)
  },
  actions: { edit: "Edit", signOff: "Sign off…", sourceDocs: "Source Docs" },
  tally: {
    mapped: "Mapped",
    review: "Need review",
    prior: "Prior-year match",
    range: "Number range",
    balanced: "TB balanced",
    of: (a: number, b: number): string => `${String(a)} of ${String(b)}`,
    pending: "Pending",
  },
  // DV-B1: the run line names the code run and carries no atom.
  runLine: (priorYear: string): string =>
    `Mapping rules ran, started by the trigger 'Trial balance pulled' · prior-year codes from the FY${priorYear} mapping`,
  runLineNone: "Mapping rules ran, started by the trigger 'Trial balance pulled'",
  review: (n: number): string => `Needs review · ${String(n)}`,
  mapped: (n: number): string => `Mapped · ${String(n)}`,
  groupBy: "Group by FS line",
  methods: {
    prior_year_match: "Prior-year match",
    number_range: "Number range",
    manual: "Edited",
  } as Readonly<Record<string, string>>,
  confidence: { high: "High", medium: "Medium" } as Readonly<Record<string, string>>,
  edited: (by: string, was: string | null): string =>
    was === null ? `Edited by ${by}` : `Edited by ${by} · was ${was}`,
  change: "Change",
  search: "Search groupings and FS lines",
  recentlyUsed: "Recently used",
  classes: {
    assets: "Assets",
    liabilities: "Liabilities",
    equity: "Equity",
    revenue: "Revenue",
    expenses: "Expenses",
  } as Readonly<Record<string, string>>,
  subtotal: (mapped: string, source: string | null): string =>
    source === null ? `Mapped ${mapped}` : `Mapped ${mapped} · TB line ${source}`,
  off: (amount: string): string => `off ${amount}`,
  tie: "tie",
  importing: {
    title: "Mapping trial balance accounts",
    body: "Matching prior-year codes, then number ranges, then descriptions…",
  },
  banners: {
    confirmed: (by: string, at: string): string =>
      `Mapping confirmed by ${by} · ${at}. Every summary line agrees to the trial balance.`,
    stale:
      "The trial balance was pulled again after you confirmed. The mapping shows 'Changed after sign-off' until it is confirmed again.", // (undesigned single-entity wording)
  },
  footer: {
    confirm: "Confirm and continue",
    openTb: "Open TB & leadsheets ›",
    note: (n: number, by: string): string =>
      `Confirming adopts all ${String(n)} mappings as shown and marks the mapping Prepared · ${by}. Balances and tie-outs are computed by code.`,
    confirmedNote: (by: string, on: string, n: number): string =>
      `Mapping confirmed by ${by} on ${on} · ${String(n)} accounts`,
  },
  dialog: {
    title: (n: number, edited: number): string =>
      edited > 0
        ? `Adopt ${String(n)} mappings (${String(edited)} edited) and mark the mapping Prepared?`
        : `Adopt ${String(n)} mappings and mark the mapping Prepared?`,
    confirm: "Confirm",
  },
  toasts: {
    changed: "Mapping changed", // (undesigned)
    confirmed: "Mapping confirmed", // (undesigned)
    failed: "That didn't save. Try again.", // (undesigned)
  },
  states: {
    empty: "No trial balance to map yet.",
    noun: "the mapping",
    flag: "Trial balance mapping",
  },
} as const;
