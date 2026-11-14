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
  // W-02-T17: the thread's fixed words (the code's notices and slots).
  nothingWritten: "Nothing was written.",
  plansOff: "I can't make changes from Workbench yet. I can read and answer; a plan to write needs plans turned on for your firm.",
  todayReadOnly: "I can't approve, sign off or send from here. Those stay with you on their own screens.",
  unavailable: "AI isn't available for real client data yet",
  turnFailed: "I couldn't finish that turn.",
  skip: "Skip",
  planReady: "Plan ready — approve?",
  viewRun: "View run",
  // W-02-T22 (DF-04): why the composer is off, and the gated tabs.
  paused: "Agents are paused for your firm.",
  consentOff: "Agents are off for this taxpayer — §7216 consent isn't on file",
  notOnTeam: "You can read this session; only its owner's team can ask here.",
  requestConsent: "Request consent",
  agentsPlanned: "Agents arrive with the agent library.",
  connectPlanned: "Connect arrives with the connector catalogue.",
  flagOff: "Workbench isn't turned on for your firm.",
} as const;
