// C-29 CommentThread, Composer and MentionPicker copy (P-05-T10; P-05 §5.5, verbatim). Menu labels
// that open a dialog end in U+2026. The ··· menus offer Correct… and Redact…, never Edit or Delete
// (DF-18).
export const COPY = {
  legend: "Comments never block sign-off. Review notes do.",
  hint: "Mentioned people are notified in Accrued and by email",
  placeholder: "Comment, or type @ to mention…",
  restricted:
    "Only people on this engagement can be mentioned. Add people in Team & roles (ENG-05).",
  pickerKeys: "↑↓ move · Enter mentions · Esc closes",
  notOnEngagement: "Not on this engagement",
  noMatch: (q: string) => `No one on this engagement matches '${q}'`,
  onEngagement: (label: string) => `On ${label}`,
  emptyTitle: "No comments yet.",
  emptyBody: "Comments are internal and never block sign-off.",
  converted: "Converted to review note · now blocks sign-off until cleared",
  sharedHint: (org: string) => `Replies here are visible to ${org}`,
  visibleTo: (org: string) => `Visible to ${org}`,
  resolve: "Resolve",
  reopen: "Reopen",
  send: "Send comment",
  more: "More actions",
  close: "Close comments",
  copyLink: "Copy link",
  toTodo: "Convert to to-do…",
  toReviewNote: "Convert to review note…",
  mute: "Mute thread",
  unmute: "Unmute thread",
  correct: "Correct…",
  redact: "Redact…",
  correctedBelow: "Corrected below",
  you: "(you)",
  resolvedBy: (name: string, time: string, n: number) =>
    `Resolved by ${name} · ${time} · ${n} ${n === 1 ? "comment" : "comments"}`,
  redactedBy: (name: string, date: string, reason: string) =>
    `Redacted by ${name} on ${date}: ${reason}`,
  notified: (names: string[], time: string) =>
    `${names.join(", ")} notified in Accrued and by email · ${time}`,
  openResolved: (open: number, resolved: number) =>
    [`Open ${open}`, `Resolved ${resolved}`] as const,
  teamCount: (label: string, n: number) => `${label} · ${n} people`,
  refused: {
    mention_not_allowed: "Someone you mentioned can't see this comment.",
    empty_comment: "Write something first.",
    comment_too_long: "That comment is too long.",
    thread_shared: "Shared threads stay comments.",
    fallback: "Couldn't post the comment. Try again.",
  },
} as const;
