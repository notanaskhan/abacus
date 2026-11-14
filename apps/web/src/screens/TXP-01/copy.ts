// TXP-01 words (T-05-T59; handoff TXP-01 spec.md and README, verbatim).
export const COPY = {
  pane: "Summary",
  railHeader: "Partnership",
  railGroup: "General Information",
  sourcesGroup: "Sources",
  memoTitle: (entity: string, year: number, form: string) =>
    `${entity} — ${String(year)} Form ${form} preparer memo`,
  edit: "Edit",
  regenerate: "Regenerate…", // opens the confirm dialog: the kit's ellipsis rule
  drafting: "Accrued Agent is drafting the memo",
  watermark: "DRAFT",
  variables: "Variables",
  approved: "Approved",
  adoptedBy: (name: string) => `Adopted by ${name}`,
  approveMemo: "Approve memo",
  adoptMemo: "Adopt memo",
  stale: (lines: readonly string[]) =>
    `Figures changed since this memo was approved (${lines.join("; ")}). Regenerate the affected sections?`,
  regenerateSections: "Regenerate sections",
  confirmTitle: "Regenerate the memo?",
  confirmBody:
    "Accrued Agent redrafts the sections whose figures moved. Sections a person wrote stay as they are.",
  confirm: "Regenerate",
  cancel: "Cancel",
  save: "Save",
  opportunities: "Opportunities",
  raise: "Raise with client…",
  planned: "Planned",
  kv: {
    entity: "Partnership",
    ein: "EIN",
    year: "Tax year",
    method: "Accounting method",
    preparer: "Preparer",
    reviewer: "Reviewer",
    signer: "Signer",
  },
} as const;
