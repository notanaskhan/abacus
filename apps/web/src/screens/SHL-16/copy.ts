// SHL-16 · Checkpoint diff drawer (P-04-T43): the handoff's words, verbatim (spec.md frames 1–6).

export const COPY = {
  title: "Checkpoints",
  segments: { checkpoints: "Checkpoints", assistant: "Assistant" },
  assistantHint: "Opens TAX-08 · assistant panel",
  filter: "Filter checkpoints",
  filters: { agent: "Agent only", named: "Named only", all: "All" },
  checkpoint: (n: number): string => `Checkpoint ${String(n)}`,
  current: "Current",
  star: "Star this checkpoint",
  unstar: "Remove the star",
  rename: "Rename",
  renameLabel: (n: number): string => `Name for Checkpoint ${String(n)}`,
  approvedBy: (name: string): string => `approved by ${name}`,
  approvedLine: (name: string, at: string): string => `Approved · ${name} · ${at}`,
  rejectedLine: (name: string, reason: string): string => `${name} · reason: ${reason}`,
  columns: { field: "Field", change: "Old → New", cause: "Cause" },
  tie: "tie",
  approve: "checkpoint",
  reject: "Reject…",
  restore: "Restore…",
  approveNote: (n: number): string =>
    `Approving makes Checkpoint ${String(n)} current. The sync chip will read 'Out of sync' until the return is exported.`,
  restoreDialog: {
    title: (n: number): string => `Restore Checkpoint ${String(n)}?`,
    body: (n: number, next: number): string =>
      `This creates Checkpoint ${String(next)} as a copy of Checkpoint ${String(n)}. Nothing is deleted, and the return will need re-export.`,
    cancel: "Cancel",
    restore: "Restore",
  },
  rejectDialog: { title: "Reject checkpoint", reason: "Reason", cancel: "Cancel", reject: "Reject" },
  emptyTitle: "No checkpoints yet.",
  emptyBody:
    "Checkpoints are saved when the agent drafts the return, when you approve changes, or when you save one by name.",
  save: "Save checkpoint…",
  toasts: {
    approved: (n: number): string => `Checkpoint ${String(n)} approved`,
    rejected: (n: number): string => `Checkpoint ${String(n)} rejected`,
    restored: (n: number): string => `Checkpoint ${String(n)} created`,
    failed: "Couldn't save. Try again.",
  },
  loading: "Loading checkpoints",
} as const;
