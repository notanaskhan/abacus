// T10 document-on-well template copy (F-06-T01): the board's chrome (screens/T10). Paper
// blocks are data (C11), never copy. Q7: labels that open a dialog carry an ellipsis.

export const COPY = {
  edit: "Edit",
  regenerate: "Regenerate…",
  approve: "Approve…",
  approved: "Approved",
  approvedBy: (actor: string, when: string): string => `Approved by ${actor} · ${when}`,
  drafting: "Accrued Agent is drafting the memo",
  // F-06-T14 (DEC-1252): a letter or email without model text renders its template only.
  rendering: "Preparing the document",
  watermark: "DRAFT",
  variables: "Variables",
  preview390: "390 preview",
} as const;
