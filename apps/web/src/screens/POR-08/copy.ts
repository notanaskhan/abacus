// POR-08's words, verbatim from the handoff (screens/POR-08 spec.md; docs/screens/POR-08.md Copy).
// Every figure, title, part, highlight, legend and decider's name is the server's: nothing here is
// a number or an entry's name. The firm's name is the brand's.

export const COPY = {
  active: "Approvals",
  title: "Approvals",
  period: "Period",
  waiting: "Waiting for you",
  posted: (period: string) => `Entries posted for ${period}`,
  approved: "Approved",
  declined: "Declined",
  comingNext: "Coming next",
  downloadEntries: "Download entries",
  view: "View",
  approve: "Approve statements",
  decline: "Decline…",
  ask: "Ask a question",
  askEntry: "Ask about this entry",
  accept: "Accept",
  acknowledge: "Acknowledge",
  review: "Review",
  reviewRequired: "Review required",
  parts: (n: number) => `${String(n)} parts`,
  waitingSub: "waiting for your approval",
  approveTitle: (title: string, client: string) =>
    client === "" ? `Approve the ${title}?` : `Approve the ${title} for ${client}?`,
  approvedBy: (who: string, when: string) => `Approved by ${who} · ${when}`,
  acceptedBy: (who: string, when: string) => `Accepted by ${who} · ${when}`,
  notRecorded: (when: string) => `Not recorded · ${when}`,
  declinedBecause: (reason: string) => `Declined · ${reason}`,
  questionSent: (when: string) => `Question sent ${when}`,
  postedEntries: (period: string, n: number) => `Entries posted for ${period} (${String(n)})`,
  attestIntro:
    "Your auditor proposes these entries. Accepting means the plan records them in its 2025 financial statements.",
  acknowledgement: (net: string, plus: string, minus: string) =>
    `If recorded, the two entries you chose not to record would increase net assets by ${net} in total (${plus} − ${minus}). They'll be listed in your representation letter, where you confirm their effect is not material, individually and in total.`,
  acknowledgementShort: (net: string) =>
    `If recorded, the entries you chose not to record would change net assets by ${net} in total. They'll be listed in your representation letter, where you confirm their effect is not material, individually and in total.`,
  // O3 decline sheet (c).
  declineTitle: "Decline statements",
  declineEntryTitle: "Decline this entry",
  reasons: {
    number_looks_wrong: "A number looks wrong",
    something_missing: "Something is missing",
    other: "Other",
  },
  note: "Note",
  entryReason: "Why not record it?",
  // The inline composer (DV-01).
  about: (title: string, amount: string | null, period: string) =>
    `About: ${amount === null ? title : `${title} ${amount}`} (${period})`,
  send: "Send",
  cancel: "Cancel",
  account: "Account",
  debit: "Debit",
  credit: "Credit",
  total: "Total",
  empty: "Nothing to approve.",
  emptyBody: (firm: string) => `${firm} will ask here when statements or an entry need your OK.`,
  // The designed flag-off state, in the words POR-09 gives its own (DEC-3130).
  flagOff: "Approvals are not on for your firm yet.",
  changed: "This item changed. Showing the current version.",
  downloadFailed: "The download didn't finish. Try again.", // POR-13's words
} as const;
