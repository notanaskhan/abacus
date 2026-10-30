// TAX-01 · Tax Returns practice board (T-02-T12): copy verbatim from the handoff's spec.md (the
// same board TPL-01 specifies). Status words come from the registry (`return`, tile labels).

export const COPY = {
  title: "Tax Returns",
  search: "Search returns",
  showing: (shown: number, total: number): string =>
    `Showing ${String(shown)} of ${String(total)} open`,
  summary: (open: number, done: number, total: number, year: number, extended: number): string =>
    `${String(open)} open · ${String(done)} done · ${String(total)} TY${String(year)} returns · ${String(extended)} extended`,
  filters: {
    form: "Form",
    office: "Office",
    partner: "Partner",
    preparer: "Preparer",
    due: "Due",
    taxYear: "Tax year",
    status: "Status",
  },
  filterAll: "All",
  allOffices: "All offices",
  next60: "Next 60 days",
  bulkActions: "Bulk actions",
  bulk: { assign: "Assign preparer…", extend: "Extend…", standards: "Run firm standards…" },
  // The handoff draws "+ New return"; it opens the new-return dialog, so the kit's ellipsis rule
  // applies and IndexList draws the "+" itself (as "New Return…" in the T1 specimen).
  newReturn: "New return…",
  columns: {
    return: "Return",
    client: "Client",
    office: "Office",
    prepRev: "Prep / Rev",
    status: "Status",
    issues: "Issues",
    sync: "Engine sync",
    // The glossary bans "deadline" as an identifier: the header says Due (F-06 Story 2.3).
    due: "Due",
    days: "Days",
    signature: "Signature",
  },
  extended: "Ext.",
  days: (n: number): string => `${String(n)} ${n === 1 ? "day" : "days"}`,
  waitingOnK1: "Waiting on K-1",
  noResults: (q: string): string => `No results for '${q}'.`,
  clearFilters: "Clear filters",
  seasonEmptyTitle: (year: number): string => `No TY${String(year)} returns yet.`,
  seasonEmptyBody: (from: number): string =>
    `Roll clients forward from TY${String(from)} to create returns, binders and assignments.`,
  openSeasonSetup: "Open season setup",
  seasonSetupTip: "Opens ENG-07 · Season setup",
  grouped: "Grouped",
  officeBand: (office: string, total: number, open: number, done: number): string =>
    `${office} · ${String(total)} returns · ${String(open)} open · ${String(done)} done`.toUpperCase(),
  select: (client: string): string => `Select ${client}`,
  selected: (n: number): string => `${String(n)} selected`,
  clear: "Clear",
  assignTo: "Assign preparer",
  assigned: (n: number): string => `${String(n)} returns assigned`,
  draftK1: "Draft K-1 · pre-release",
  draftK1Detail:
    "Ridgeline Property Partners, LP K-1 · Draft K-1 · pre-release · final pending Ridgeline approval",
  openTxp12: "Open K-1 package",
  openTxp12Tip: "Opens TXP-12 · Ridgeline K-1 package",
  syncTip: "Opens TAX-09 · Tax-engine sync",
  signerTip: "Opens SIG-01 · the envelope",
  dueRule: (client: string): string => `Due date rule for ${client}`,
  error: "Tax returns couldn't load.",
} as const;
