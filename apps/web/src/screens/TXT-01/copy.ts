// TXT-01 copy, verbatim from the handoff (TXT-01-governing-instrument-trust-profile.md) and
// docs/screens/TXT-01.md. Status words come from the registry (C2), never from here.

export const COPY = {
  profile: "Trust profile",
  approve: "Approve interpretation",
  approved: "Approved",
  approvedBy: (name: string, day: string): string => `Approved · ${name} · ${day}`,
  band: (year: number): string => `Determinations · ${String(year)}`,
  proposedByAgent: "Proposed by Accrued Agent",
  citedBy: "Cited by",
  record: "Record…",
  clauseRequired: "Needs a clause",
  rows: {
    trust: "Trust",
    agreement: "Agreement",
    settlor: "Settlor",
    ein: "EIN",
    residency: "Residency",
    taxYear: "Tax year",
    due: "Due",
  },
  taxYear: (year: number): string => `Calendar ${String(year)}`,
  due: (day: string, extended: boolean): string => (extended ? `${day} (extended)` : day),
  agreement: (day: string, irrevocable: boolean): string =>
    irrevocable ? `${day} (irrevocable)` : day,
  settlor: (name: string, died: number | null | undefined): string =>
    died == null ? name : `${name} (died ${String(died)})`,
  residency: (state: string, form: string | null | undefined): string =>
    form ? `${state} resident trust → ${form}` : `${state} resident trust`,
  footer: (
    read: string | null,
    count: number,
    citations: number,
    adopted: string | null,
  ): string =>
    [
      read === null ? null : `Read by Accrued Agent ${read}`,
      `${String(count)} determinations`,
      `${String(citations)} clause citations`,
      adopted === null ? null : `adopted by ${adopted}`,
    ]
      .filter((p) => p !== null)
      .join(" · "),
  unread: {
    title: "Instrument not read yet",
    body: "Run the instrument reader to extract the trust's tax determinations.",
    read: "Read instrument",
  },
  agentsOff: "The reader is off for this firm: record each determination with its clause.",
  consent: (trust: string, signed: number, required: number): string =>
    `§7216 AI consent — ${trust} (${String(signed)} of ${String(required)} signed)`,
  reader: {
    menu: "Document actions",
    download: "Download",
    openInFiles: "Open in Files",
    zoomOut: "Zoom out",
    fit: "Fit",
    zoomIn: "Zoom in",
    rotate: "Rotate",
    previous: "Previous page",
    next: "Next page",
    page: (n: number, total: number): string => `${String(n)} / ${String(total)}`,
    highlight: "Highlight colour",
    search: "Search",
    searchPlaceholder: "Search the agreement",
    citedBy: "Cited by",
    noText: "This page has no readable text yet.",
  },
} as const;
