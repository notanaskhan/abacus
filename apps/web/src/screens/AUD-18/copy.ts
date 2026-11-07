// AUD-18 · EQR workspace (A-07-T17): every word verbatim from the handoff.

export const COPY = {
  rail: "EQR checklist",
  overview: {
    subtitle: (name: string | null | undefined) => `PY2025 · EQR ${name ?? ""}`,
    complete: (a: number, b: number) => `${String(a)} of ${String(b)} complete`,
  },
  band: "Checklist",
  canvas: "Significant judgments",
  built: (n: number) => `Built from ${String(n)} decision cards`,
  sourceDocs: "Source Docs",
  markReviewed: "Mark reviewed ✓",
  reviewed: "Reviewed",
  readOnly: "EQR · read-only",
  dock: { notes: "Notes", agent: "Agent" },
  note: {
    open: "Open",
    responded: "Responded",
    cleared: "Cleared",
    assigned: (n: string) => `Assigned to ${n}`,
    clear: "✓ Clear",
    reopen: "Reopen",
    add: "Add EQR note…",
  },
  concurrence: {
    title: "Concurrence · G6",
    blocked: (items: number, notes: number) =>
      `Blocked: ${String(items)} checklist items open · ${String(notes)} EQR notes not cleared.`,
    ready: "All 10 items complete. Notes cleared.",
    action: "Concur…",
    done: (date: string, name: string) => `Concurred · ${date} · ${name}`,
    met: "G6 ✓",
  },
  notEqr: "Only the assigned EQR can concur.",
  sheet: {
    title: "Concur with the engagement team's significant judgments",
    attest: "I was not involved in performing this engagement",
    date: "October 5, 2026",
    concur: "Concur",
    cancel: "Cancel",
  },
  agent: {
    tool: "Assemble judgments digest",
    narration:
      "I built the digest from 6 decision cards and 3 conclusions. I have not evaluated them.",
  },
} as const;
