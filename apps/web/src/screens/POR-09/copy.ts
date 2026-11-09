// POR-09's words, verbatim from the handoff (screens/POR-09 spec.md; R-02 §3.2). Every figure and
// title is the server's: nothing here is a number or a document's name.

export const COPY = {
  active: "Deliverables",
  title: "Deliverables",
  comingNext: "Coming next",
  myK1s: "My K-1s",
  draftForReview: "Draft for review",
  downloadDraft: "Download draft",
  download: "Download",
  approve: "Approve statements…",
  approveMobile: "Approve statements",
  approveTitle: "Approve the 2025 financial statements (the latest draft)?",
  approveConfirm: "Approve statements",
  approvedNote: "Brightwater Hale will release the final statements with the report.",
  newerDraft: "A newer draft is available",
  comments: (n: number) => `Comments · ${String(n)}`,
  composer: "Comment on this page…",
  composerHint: "Click anywhere on a page to add a comment.",
  page: (n: number, of: number) => `${String(n)} / ${String(of)}`,
  previous: "Previous page",
  next: "Next page",
  zoomOut: "Zoom out",
  fit: "Fit",
  zoomIn: "Zoom in",
  legend: "Prepared by Brightwater Hale. No assurance is provided.",
  approveInApprovals: "Approve in Approvals →",
  empty: "Nothing delivered yet.",
  emptyBody: "Finished documents from Brightwater Hale will appear here.",
  // The designed flag-off state, in the words EBP-08 gives its own (DEC-3130).
  flagOff: "Deliverables are not on for your firm yet.",
  k1Added: "We've also added this K-1 to your own 2025 return.",
  k1Ownership: "Ownership",
  downloadFailed: "The download didn't finish. Try again.", // POR-13's words
  approvedBy: (day: string) => `Approved by you · ${day}`,
  k1Released: (day: string) => `Released ${day}`,
} as const;
