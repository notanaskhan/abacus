// NOT-01 copy, verbatim from the handoff spec (NOT-01-notices-index-intake-sheet.md) and
// docs/screens/NOT-01.md. Status words come from the registry (C2), never from here.

export const COPY = {
  title: "Notices",
  noun: "notices",
  search: "Search notices",
  addNotice: "Add notice",
  chips: {
    agency: "Agency",
    notice: "Notice",
    assignee: "Assignee",
    respondBy: "Respond by",
    all: "All",
    anyone: "Anyone",
    any: "Any",
  },
  agencies: { irs: "IRS", state: "State" },
  types: { cp2000: "CP2000", cp14: "CP14", cp501: "CP501", state: "State" },
  windows: { 7: "Within 7 days", 30: "Within 30 days" },
  byType: "By type",
  /** "9 open · 1 due within 7 days · 1 blocked (no authorization)" */
  summary: (open: string, due: string, blocked: string): string =>
    `${open} open · ${due} due within 7 days · ${blocked} blocked (no authorization)`,
  columns: {
    client: "Client",
    agency: "Agency",
    notice: "Notice",
    taxYear: "Tax year",
    received: "Received",
    respondBy: "Respond by",
    amount: "Amount",
    status: "Status",
    assignee: "Assignee",
    authorization: "Authorization",
  },
  days: (n: number): string => `${String(n)} ${n === 1 ? "day" : "days"}`,
  sent: (day: string): string => `Response sent ${day}`,
  interest: (v: string): string => `+ ${v} interest`,
  disagreed: "disagreed",
  agent: {
    name: "Notice Intake & Response Drafter",
    onArrival: "on arrival",
    stage: { off: "Off", shadow: "Shadow", live: "Live", refused: "Off" },
  },
  empty: {
    title: "No open notices.",
    body: "Notices uploaded by clients, forwarded to the Inbox or scanned in the mailroom appear here.",
  },
  noMatch: (q: string): string => `No results for '${q}'.`,
} as const;
