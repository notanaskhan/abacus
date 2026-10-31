// HOME-02 · My approvals & review queue (I-01-T16, T17): the queue's and the detail pane's copy,
// verbatim from the handoff's spec.md and docs/screens/HOME-02.md (Copy); band titles and due words
// are HOME_MESSAGES (domain/home), shared with HOME-01. Strings marked (undesigned) are composed
// from the existing kits where the handoff draws nothing.

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
  detailPane: {
    loading: "Loading…",
    missing: "This item couldn't load.", // (undesigned)
    reservedTo: "Reserved to",
    proposedBy: "Proposed by",
    workItem: "Work item",
    due: "Due",
    level: "Level",
    workpaper: "Workpaper",
    prepared: "Prepared",
    reviewed: "Reviewed",
    why: "Why This Was Surfaced",
    evidence: "Evidence",
    source: "Source",
    reasoning: "Reasoning",
    recommendation: "Agent recommendation",
    rationaleLabel: "Rationale",
    rationalePlaceholder: "Why you decided this (kept with the decision)",
    requestMore: "Request more analysis…",
    reassign: "Reassign…",
    snooze: "Snooze until…",
    signOff: "Sign off…",
    openProposal: "Open proposal",
    approveAdjustments: "Approve adjustments",
    reject: "Reject…",
    finalApproval: "Final approval…", // (undesigned: SHL-12's final approval opens from here)
    send: "Send…", // (undesigned: SIG-01 "To send")
    agent: "Accrued Agent",
    agentCannotApprove: "The agent cannot approve its own work.",
    decisionRecorded: "Decision recorded",
    decideFailed: "The decision wasn't recorded. Try again.", // (undesigned)
    run: (by: string, on: string): string =>
      by === ""
        ? `Accrued Agent · ${on}`
        : `Accrued Agent · run by ${by}${on === "" ? "" : ` · ${on}`}`,
    decided: (person: string, at: string): string => `Decided · ${person} · ${at}`,
    reservedLine: (role: string): string => `Reserved to the ${role}. The agent cannot decide.`,
    reservedValue: (person: string, role: string): string => `${person} · ${role}`,
    version: (label: string, n: number): string => `${label} · Version ${String(n)}`,
    signed: (word: string, initials: string): string => `${word} · ${initials}`,
    signsAt: (level: string): string => `Signs off at ${level}.`,
    citations: (n: number): string => `${String(n)} citation${n === 1 ? "" : "s"}`,
    blocked: (check: string, off: string, fix: string, awaits: string): string =>
      `Cannot sign off: ${check} · off ${off}. The fix (${fix}) is proposed by Accrued Agent and awaits ${awaits}.`,
    blockedOther: "Cannot sign off yet: a check is open.", // (undesigned)
    title: (section: string, work: string): string => `${section} — ${work}`,
  },
  evidencePane: {
    sources: "Evidence sources",
    openSource: "Open source",
  },
  /** The reserved role in a sentence ("the engagement partner") and as a value. */
  roles: {
    engagement_partner: { line: "engagement partner", value: "Engagement partner" },
    signer: { line: "signer", value: "Signer" },
    manager: { line: "manager", value: "Manager" },
    eqr_reviewer: { line: "EQR reviewer", value: "EQR reviewer" },
  } as Readonly<Record<string, { line: string; value: string }>>,
  levels: {
    L1_preparer: "Preparer (L1)",
    L2_reviewer: "Reviewer (L2)",
    L3_manager: "Manager (L3)",
    L4_partner: "Partner (L4)",
    L5_eqr: "EQR (L5)",
  } as Readonly<Record<string, string>>,
} as const;
