// AUD-17 · Review notes & sign-off matrix (A-06-T24): every word verbatim from the handoff.

export const COPY = {
  queue: "Review notes",
  showCleared: "Show cleared",
  bands: { open: "Open", responded: "Responded", cleared: "Cleared" },
  status: {
    open: "Open",
    responded: "Responded",
    cleared: "Cleared",
    closed: "Closed",
    withdrawn: "Withdrawn",
  },
  kv: { anchor: "Anchor", author: "Author", status: "Status", opened: "Opened" },
  reply: "Reply…",
  send: "Send",
  clear: "✓ Clear note",
  reopen: "Reopen",
  cleared: "Note cleared",
  empty: {
    title: "No review notes.",
    body: "Notes anchored to cells, sections and documents appear here.",
  },
  staleNotice: "This paper changed after a sign-off — re-review required.",
  matrix: {
    title: "Sign-off matrix",
    segments: { matrix: "Matrix", involvement: "EP involvement" },
    workpaper: "Workpaper",
    levels: ["L1 Preparer", "L2 Reviewer", "L3 Manager", "L4 Partner", "L5 EQR"],
    groups: {
      planning: "PLANNING",
      fieldwork: "FIELDWORK & TESTING",
      completion: "COMPLETION",
      reporting: "REPORTING",
    },
    footer: (p: {
      workpapers: number;
      prepared: number;
      reviewed: number;
      partner: string;
      eqr: string;
      changed: number;
    }): string =>
      `${String(p.workpapers)} workpapers · Prepared ${String(p.prepared)} · Reviewed ${String(p.reviewed)} · Partner ${p.partner} · EQR ${p.eqr} · Changed after sign-off ${String(p.changed)}`,
    staleTitle: "Changed after sign-off",
    staleBody: "Content hash changed",
    requestReReview: "Request re-review",
    legend: "A review note blocks sign-off; a comment never does.",
    notRequired: "—",
  },
} as const;
