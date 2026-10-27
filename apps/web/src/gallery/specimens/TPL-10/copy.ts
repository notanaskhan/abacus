// TPL-10 Ridgeline preparer memo specimen copy (F-06-T01): verbatim from the handoff
// (screens/TPL-10, spec.md). Memo paragraphs and figures are seed data
// (fixtures/seed/tax/ridgeline.ts); the letter's clauses are letters.ts.

export const COPY = {
  sheetHeader: "Partnership › General Information",
  kv: {
    status: "Status",
    partnership: "Partnership",
    ein: "EIN",
    activity: "Principal activity",
    method: "Accounting method",
    taxYear: "Tax year",
    partners: "Partners",
    allocation: "Allocation",
    extension: "Extension",
    due: "Due",
    engineReturn: "Engine return",
    client: "Client",
    engagement: "Engagement",
    binder: "Binder",
    files: "Files",
    preparer: "Preparer",
    reviewer: "Reviewer",
    signer: "Signer",
    created: "Created",
  },
  paperTitle: "Preparer memo",
  edit: "Edit",
  regenerate: "Regenerate…",
  // Q7: opens SHL-12, so it carries the ellipsis (DECISIONS.md, F-06-T01).
  approveMemo: "Approve memo…",
  approved: "Approved",
  headings: [
    "Facts",
    "Structural events",
    "Book-to-tax bridge",
    "Depreciation",
    "States and PTET",
    "Distributions",
    "Open items",
    "Opportunities",
  ],
  meta: "Drafted by Accrued Agent · adopted by Olivia Brandt, Sep 10, 2026 · Reviewer: Samuel Ito",
  // Q6: adoption is a sub-line fact, never a status.
  adoptedBy: (name: string): string => `Adopted by ${name}`,
  approvedBy: (actor: string, when: string): string => `Approved by ${actor} · ${when}`,
  drafting: "Accrued Agent is drafting the memo",
  letterheadName: "Brightwater Hale LLP",
  letterheadAddress: "311 West Brannock Street, Chicago, IL",
  watermark: "DRAFT",
  variables: "Variables",
} as const;
