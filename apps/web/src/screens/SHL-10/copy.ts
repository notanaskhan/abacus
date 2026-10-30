// SHL-10 · Approve agent output (P-04-T41): the handoff's words, verbatim where it gives them
// (spec.md frames a, b, c and f; revision.md R2).
import type { RejectReason } from "../../domain/review";

export const COPY = {
  title: "Approve agent output",
  proposed: (n: number) => `proposed ${String(n)} ${n === 1 ? "change" : "changes"}`,
  reasoning: "Reasoning",
  head: { field: "Field", change: "Before → After", cause: "Cause" },
  unsupported: "Unsupported",
  tie: "tie",
  citations: (n: number) => `${String(n)} ${n === 1 ? "citation" : "citations"}`,
  uncited: (n: number) =>
    `${String(n)} ${n === 1 ? "change has" : "changes have"} no citation. Remove it or ask the agent to cite a source.`,
  approveObject: "adjustments",
  approveEdits: "with edits",
  edit: "Edit…",
  cancelEdit: "Cancel edits",
  reject: "Reject…",
  followUp: "Ask follow-up…",
  footnote: "Approving creates a checkpoint and logs to Activity.",
  citationNote: "Citation note",
  citationRequired: "Required",
  rejectDialog: {
    title: "Reject proposal",
    reason: "Reason",
    note: "Note",
    cancel: "Cancel",
    reject: "Reject",
  },
  reasons: {
    wrong_treatment: "Wrong treatment",
    unsupported_value: "Unsupported value",
    needs_client_input: "Needs client input",
    other: "Other",
  } satisfies Record<RejectReason, string>,
  followUpDialog: {
    title: "Ask follow-up",
    label: "Your question",
    sent: "Follow-up sent to the agent",
  },
  rejected: (by: string, reason: string) => `Rejected by ${by} · reason: ${reason}`,
  approved: (by: string) => `Approved by ${by}`,
  toasts: {
    approved: "Proposal approved",
    rejected: "Proposal rejected",
    failed: "Couldn't save. Try again.",
    changed: "The agent revised this proposal. Review the new version.",
  },
  // d, e, e′, g (P-04-T42; spec frames D and E, R2 frame G).
  proposedEntries: (n: number, policy: string) => `proposed ${String(n)} entries within ${policy}`,
  approveBatch: (n: number, policy: string) => `${String(n)} under ${policy}`,
  approveConclusion: "conclusion",
  batchTitle: (n: number) => `Approve ${String(n)} entries`,
  sendTo: (name: string) => `Send to ${name} for approval`,
  sentTo: (name: string) => `Sent to ${name} for approval`,
  yourLimit: "Your limit: within-threshold batches only.",
  approvedUnder: (by: string, policy: string, at: string) =>
    `✓ Approved by ${by} under ${policy} · ${at}`,
  undo: "Undo",
  undone: "Approval undone",
  je: { entry: "Entry", debit: "Debit", credit: "Credit", policy: "Policy" },
  setRow: (label: string, results: number, exceptions: number) =>
    `Part of ${label} · ${String(results)} results · ${String(exceptions)} ${exceptions === 1 ? "exception" : "exceptions"}`,
  reviewAll: "Review all in package",
  reviewAllHint: "Opens SHL-19 on this set",
  loading: "Loading the proposal",
  missing: "This proposal isn't available.",
} as const;
