// INB-01 · Inbox (N-01-T10; docs/screens/INB-01.md; handoff INB-01 spec.md, TPL-08). Verbatim.
export const COPY = {
  title: "Inbox",
  mailbox: "docs@brightwaterhale.com",
  search: "Search messages",
  showIgnored: "Show ignored",
  showFiled: "Show filed",
  logIntake: "Log received documents…",
  // INB-02's sheet title, as the reading header's File… item (N-01-T23).
  fileAttachments: "File attachments…",
  summary: (waiting: number, unmatched: number): string =>
    `${String(waiting)} waiting · ${String(unmatched)} unmatched`,
  empty: {
    title: "No messages match these filters",
    body: "Widen the date range or clear a filter to see more of the inbox.",
    clear: "Clear filters →",
  },
} as const;
