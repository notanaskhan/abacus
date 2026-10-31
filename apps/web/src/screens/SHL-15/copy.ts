// SHL-15 · Issue composer & fix instructions (P-04-T54): copy verbatim from the handoff's spec.md and
// artboards; strings marked (undesigned) are composed where the handoff draws nothing.

export const COPY = {
  fixTitle: "Fix instructions",
  newTitle: "New issue",
  bulkTitle: (n: number): string => `Instructions for ${String(n)} issues`,
  position: (n: number, of: number): string => `Issue ${String(n)} of ${String(of)}`,
  close: "Close",
  loading: "Loading…",
  missing: "This issue couldn't load.", // (undesigned)
  kv: {
    class: "Class",
    priority: "Priority",
    assignedTo: "Assigned to",
    assignee: "Assignee",
    linked: "Linked",
    title: "Title",
    clientContact: "Client contact",
  },
  kinds: {
    missing_information: "Missing information",
    action_required: "Action required",
    review_point: "Review point",
    waiting_on_client: "Waiting on client",
    exception: "Exception",
    engine_diagnostic: "Engine diagnostic",
  } as Readonly<Record<string, string>>,
  /** The four classes a person picks from in the composer (blueprint §3.3.1). */
  pickable: [
    "missing_information",
    "action_required",
    "review_point",
    "waiting_on_client",
  ] as const,
  priorities: { high: "High", medium: "Medium", low: "Low" } as Readonly<Record<string, string>>,
  agent: "Accrued Agent",
  you: (name: string): string => `${name} (you)`,
  suggested: "Suggested by Accrued Agent",
  useSuggestion: "Use suggestion",
  instructions: "Instructions",
  applyTo: "Apply to",
  thisIssue: "This issue only",
  allOfClass: (n: number, kind: string): string =>
    `All ${String(n)} ${kind} issues on this return`,
  scopeLocked: (n: number): string => `Applies to the ${String(n)} selected issues only`,
  cancel: "Cancel",
  setFix: "Set Fix Instructions",
  setFixFor: (n: number): string => `Set Fix Instructions for ${String(n)}`,
  fixSet: "Fix instructions set", // (undesigned toast)
  agentsOff:
    "The agent can't take fix instructions right now: no fix runner is on for this firm. Assign the issue to a person instead.", // (undesigned)
  failed: "That didn't save. Try again.", // (undesigned)
  issue: "Issue",
  internalNote: "Internal note",
  clientWording: (first: string): string => `Client wording — what ${first} sees`,
  createIssue: "Create issue",
  createAndSend: "Create & send to client",
  sendsAs: (first: string): string =>
    `Sends as a request in ${first}'s portal (POR-04). Internal notes stay internal.`,
  issuesCount: (context: string, from: number, to: number): string =>
    `${context} Issues ${String(from)} → ${String(to)}`.trim(),
  created: "Issue created", // (undesigned toast)
  sent: (first: string): string => `Sent to ${first}`, // (undesigned toast)
  issues: "Issues",
  // The T9 detail of one issue (a′, a″, d).
  explain: "Explain…",
  inProgress: "In progress — agent fixing",
  running: "Running",
  proposedChanges: (n: number): string =>
    `Proposed ${String(n)} change${n === 1 ? "" : "s"} for your approval`,
  proposedBy: "Proposed by Accrued Agent · waiting for your approval",
  accept: "Accept",
  explanation: "Explanation",
  explainedBy: (at: string): string => `Accrued Agent · ${at}`,
} as const;
