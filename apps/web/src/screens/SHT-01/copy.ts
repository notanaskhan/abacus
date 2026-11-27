// SHT-01's words, verbatim from the handoff (screens/SHT-01 spec.md) where it words them.
export const COPY = {
  allAudits: "All Audits",
  defaultView: "Default view",
  selectRows: "Select the rows to sign off first.",
  failed: "The sheet could not load.",
  retry: "Retry",
  // K-03-T22: state e, the row drawer.
  conclusion: {
    properly_excluded: "Properly excluded",
    properly_included: "Properly included",
    improperly_excluded: "Improperly excluded",
    needs_input: "Needs input",
  },
  drawer: {
    tabsLabel: "Row",
    tabs: {
      details: "Details",
      comments: "Comments",
      agents: "Agents",
      evidence: "Evidence",
      requests: "Requests",
      todos: "To-dos",
    },
    conclusion: "Conclusion",
    why: "Why",
    suggestedAtom: "Suggested by Accrued Agent · not yet adopted",
    adopt: "Adopt (L1)",
    raiseException: "Raise exception…",
    finished: (day: string, at: string) => `finished ${day}, ${at}`,
    linked: (day: string) => `Linked ${day}`,
    linkKind: { evidence: "Evidence", request: "Request" },
    noAgents: "No agent has run on this row.",
    noEvidence: "No evidence linked.",
    noRequests: "No requests linked.",
    noTodos: "No to-dos",
    notFound: "This row could not load.",
  },
};
