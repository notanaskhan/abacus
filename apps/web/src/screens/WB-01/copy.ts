// WB-01 copy, verbatim from the handoff spec (W-02 §2.1, AC-L3, AC-L4, AC-V1). Filter words are
// C2's (`workbench_session_filter`), never typed here.
export const COPY = {
  sessions: "Sessions",
  search: "Search",
  noMatch: (q: string) => `No sessions match '${q}'.`,
  clearSearch: "Clear search",
  deleteConfirm: "Delete this session? Its run trace stays in the firm audit log.",
  delete: "Delete",
  lockedTitle: "You can't open this session",
  lockedBody: (client: string, contacts: readonly string[]) =>
    `It reads ${client}, a client you don't have access to. ${contacts.join(" or ")} can share what you need.`,
} as const;
