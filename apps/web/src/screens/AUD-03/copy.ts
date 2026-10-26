// AUD-03 copy, verbatim from the handoff spec.md and revision.md R2 (docs/screens/AUD-03.md, Copy).
// Row text (request titles, file paths, category names, who owes a request) is data, never copy.
// The few strings no artboard draws are marked, with their decision.

export const COPY = {
  canvas: {
    title: "Source Documents",
    add: "+ Add",
    filter: "Filter",
    remind: "Remind…",
    search: "Search",
    missingFirst: "Missing first",
    receivedFirst: "Received first",
    nothingMissing: "Nothing missing",
    // Not drawn (DEC-341, as AUD-02): an empty search and an audit with no requests.
    noMatch: (q: string) => `No documents match ‘${q}’.`,
    empty: "No requests yet",
  },
  group: {
    count: (received: number, total: number) => `${String(received)} of ${String(total)}`,
    sampleDriven: "Sample-driven · 0",
    sampleNote: "Item requests are generated after Sample Selection.",
  },
  row: {
    requested: (on: string, due: string | null, owedBy: string | null) =>
      [`Requested ${on}`, due === null ? null : `due ${due}`, owedBy]
        .filter((p) => p !== null)
        .join(" · "),
    received: "Received",
    needsReview: "Uploaded – needs review",
    overdue: "Overdue",
    returned: (reason: string) => `Returned · ${reason}`,
    uploaded: (on: string) => `uploaded ${on}`,
    matched: (n: number) => `matched ${String(n)}%`,
    /** c: the matcher's proposal ("Schedule of Account Balances ← … · match 62%"). */
    proposal: (title: string, path: string, n: number) =>
      `${title} ← ${path} · match ${String(n)}%`,
    linked: (n: number) => `Linked (${String(n)})`,
    noLinks: "—",
    menu: "More actions",
    openInFiles: "Open in Files",
    replace: "Replace",
    unlink: "Unlink",
    screening: {
      passed: "Evidence screening · Passed",
      flagged: "Evidence screening · Flagged",
      not_screened: "Evidence screening · Not screened",
    },
  },
  viewer: {
    title: "Viewer",
  },
  strip: {
    match: (n: number) => `Match ${String(n)}%`,
    return: "Return…",
    accept: "Accept",
    // Not drawn (DEC-421): the toast rules' wording after Accept.
    accepted: (title: string) => `${title} accepted`,
    failed: "Couldn’t accept the file",
  },
  empty: {
    notReceived: "Not received yet",
    requested: (on: string, owedBy: string | null, due: string | null) =>
      [
        owedBy === null ? `Requested ${on}` : `Requested ${on} from ${owedBy}`,
        due === null ? null : `due ${due}`,
      ]
        .filter((p) => p !== null)
        .join(" · "),
    /** g: "Requested Sep 1 from Dana Kowalski · due Sep 18 · overdue" in red ink. */
    overdue: "overdue",
    remind: "Remind",
    thirdParty: "Request from third party…",
  },
  /** "Request from third party…": SHL-14's third-party words (DEC-422). */
  thirdParty: {
    title: "Request from a third party",
    field: "Third party",
    help: (delegate: string, assignee: string) =>
      `${delegate} sees only this request (POR-14). ${assignee} is copied.`,
    send: (name: string) => `Send to ${name}`,
    // Not drawn (DEC-422): the toast rules' wording.
    sent: (name: string) => `Requested from ${name}`,
    failed: "Couldn’t request it from the third party",
  },
  notFound: "This audit isn't available.",
} as const;
