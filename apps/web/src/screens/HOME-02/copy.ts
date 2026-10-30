// HOME-02 · My approvals & review queue (I-01-T16): the queue's copy, verbatim from the handoff's
// spec.md; band titles and due words are HOME_MESSAGES (domain/home), shared with HOME-01.

export const COPY = {
  title: "Approvals",
  waiting: "Waiting on you",
  showDone: "Show done",
  hideDone: "Show open",
  done: "Done",
  sort: "Sort",
  deadline: "Deadline",
  select: "Select",
  empty: "Nothing waiting on you.",
  evidence: "Evidence",
  detail: "Detail",
  queue: "Approvals queue",
  open: "Open",
  selected: (title: string): string => `Selected: ${title}`,
  glyph: {
    decision: "Decision",
    sign_off: "Sign-off",
    blocked: "Blocked",
    other: "Approval",
  },
  error: "The queue couldn't load.",
} as const;
