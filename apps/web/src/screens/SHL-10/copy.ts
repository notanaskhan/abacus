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
  loading: "Loading the proposal",
  missing: "This proposal isn't available.",
} as const;
