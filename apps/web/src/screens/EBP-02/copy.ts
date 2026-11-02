// EBP-02 · Plan provisions review (A-05-T17): copy verbatim from the handoff spec.
export const COPY = {
  title: "Plan Review",
  version: (n: number): string => `Version ${String(n)}`,
  edit: "Edit",
  signOff: "Sign off…",
  sourceDocs: "Source Docs",
  block: "Plan Provisions Review",
  verified: (done: number, total: number): string =>
    `${String(done)} of ${String(total)} verified`,
  agentDraft: "Agent draft",
  columns: { provision: "Provision", election: "Plan election", reference: "Plan doc reference" },
  verify: (label: string): string => `Verify ${label}`,
  verifiedBy: (label: string, initials: string): string => `${label} verified by ${initials}`,
  citations: (n: number): string => `Citations (${String(n)})`,
  procedures: "Procedures (1)",
  signOffReason: "Verify every provision before signing off",
  reviewed: (initials: string, on: string): string => `Reviewed · ${initials} ${on}`,
  raise: "Raise exception…",
  snapshot: "Read-only: the provisions read before the 2024 amendment",
  diff: (n: number): string => `+${String(n)} rows`,
  empty: "No plan review yet",
  emptyBody: "Begin a plan review from the plan documents to read its provisions.",
} as const;
