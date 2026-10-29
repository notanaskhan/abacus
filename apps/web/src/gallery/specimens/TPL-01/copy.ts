// TPL-01 Tax Returns practice-board specimen copy (F-06-T01): verbatim from the handoff
// (screens/TPL-01, spec.md). Status words are not here: they come from the registry through
// StatusPill object="return" (tile "Issues" is action_required's home_and_tax_tiles label).

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
} as const;
