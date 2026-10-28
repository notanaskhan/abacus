// SIG-01 · Signatures hub (N-02-T11; docs/screens/SIG-01.md "Copy"; handoff SIG-01 spec.md).
// Verbatim; strings marked "(pending counsel)" in the contract stay as drawn until counsel signs.
export const COPY = {
  title: "Out for signature",
  noun: "envelopes",
  search: "Search envelopes",
  tabs: {
    label: "Envelopes",
    toSend: "To send",
    out: "Out for signature",
    completed: "Completed",
    expired: "Expired",
  },
  tiles: {
    sent: "Sent",
    viewed: "Viewed",
    partiallySigned: "Partially signed",
    due: "Due ≤ 7 days",
  },
  summary: "17 out · 10 gate e-file · 4 gate engagements",
  columns: {
    envelope: "Envelope",
    signers: "Signers",
    sent: "Sent",
    viewed: "Viewed",
    due: "Due",
    workItem: "Work item",
    status: "Status",
  },
  datedAsOf: "Dated as of report date",
  days: (n: number): string => (n === 1 ? "1 day" : `${String(n)} days`),
  remind: "Remind selected…",
  newEnvelope: "+ New envelope",
  reviewSend: "Review & send…",
  drafted: (on: string, by: string): string => `drafted ${on} by ${by}`,
  empty: {
    title: "Nothing to send.",
    body: "Envelopes you draft from returns, letters and notices wait here.",
  },
  drawer: {
    evidence: "Evidence",
    download: "Download evidence",
    envelope: "Envelope",
    workItem: "Work item",
    sent: "Sent",
    due: "Due",
    retention: "Retention",
    retentionText:
      "Keep 7 years (minimum: 3 years from the return due date or IRS received date, whichever is later — Pub 1345)",
  },
  df11: {
    needsHandwritten: "Needs a handwritten signature",
    upload: "Upload signed 8879…",
  },
  menu: { label: "Envelope actions", void: "Void…" },
} as const;
