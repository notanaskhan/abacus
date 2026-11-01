// SHL-09 · Field provenance tray copy (P-04-T55): verbatim from the handoff (SHL-09 spec, frames
// 1–6). Values, citations, references, names and notes are server data; these are the words
// around them. Strings marked (undesigned) are composed from the existing kits.

export const COPY = {
  label: "Field provenance",
  updated: "Updated",
  previous: "Previous",
  value: "Value",
  citation: "Citation",
  references: "References",
  signOffs: "Sign-offs",
  editValue: "Edit value",
  collapse: "Collapse",
  expand: "Expand",
  edited: "Edited",
  estimate: "≈",
  estimateLabel: "Estimate",
  noSource: "No source cited",
  unsupported: "Unsupported",
  changedAfter: "Changed after sign-off",
  beforeChange: "(before this change)",
  versions: (n: number): string => `${String(n)} version${n === 1 ? "" : "s"}`,
  signOffField: "Sign off field",
  addReference: "Add reference",
  addReferenceFirst: "Add a reference before signing off",
  openIssue: (title: string): string => `Open issue: ${title}`,
  openIssueBare: "Open issue", // (undesigned: the issue's title has not loaded)
  jump: (label: string): string => `Go to ${label}`,
  addTo: (label: string): string => `Add ${label} as a reference`,
  sub: (when: string, who: string): string => `${when} · ${who}`,
  tick: (initials: string, on: string): string => `✓ ${initials} · ${on}`,
  flag: (initials: string, on: string): string => `⚑ ${initials} · ${on}`,
  edit: {
    value: "Value",
    note: "Citation note (required)",
    save: "Save",
    cancel: "Cancel",
    failed: "That change wasn't saved. Try again.", // (undesigned)
  },
  pick: {
    title: "Documents in this return",
    none: "No documents to add", // (undesigned)
  },
  toasts: {
    signed: "Field signed off", // (undesigned)
    saved: "Value saved", // (undesigned)
    referenced: "Reference added", // (undesigned)
  },
} as const;
