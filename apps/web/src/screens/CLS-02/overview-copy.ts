// CLS-02 Overview's words (C-01-T34), verbatim from the handoff (CLS-02-close-overview-run.md,
// states A to E). Figures come from the read model (`GET /v1/closes/{id}` and the run), never
// from here; the status words come from the registry.

export const OVERVIEW = {
  rail: "Summary",
  canvas: "Overview",
  stats: {
    openIssues: "Open Issues",
    documents: "Documents in Binder",
    reconciled: "Accounts Reconciled",
    pastDue: "Past Due",
    due: "Due",
  },
  details: "Details",
  detailRows: {
    client: "Client",
    engagement: "Engagement",
    period: "Period",
    plan: "Close Plan",
    planLink: "View Plan",
    files: "Files",
  },
  review: "Review and Delivery",
  reviewRows: { due: "Due Date", preparers: "Preparers", reviewers: "Reviewers" },
  portal: "Client Portal",
  portalRows: {
    contact: "Contact",
    status: "Status",
    portal: "Portal",
    portalLink: "Client Portal",
    requests: "Requests",
    messages: "Messages",
    reminder: "Reminder",
    reminderLink: "Draft Email",
  },
  runningTitle: "Close agent is running",
  runningSub: "3 tasks running at once.",
  completeTitle: "Close agent completed",
  idleTitle: "Close agent",
  waitingTitle: "Close agent",
  waiting: "Waiting on 1 answer",
  failedTitle: "Stopped at Shopify",
  failedBody: "The payout report covers Aug 1–29; Aug 30–31 payouts are missing",
  run: "Run",
  runPrimary: "Run",
  retry: "Retry",
  viewRun: "View run",
  viewWork: "View work",
  composer: "Ask the close agent…",
  runningPill: "Running closing agent",
  runMenu: { all: "Run all tasks", group: "Run this group", failed: "Run failed tasks" },
  historyRun: (n: number) => `Run ${String(n)}`,
  statusMenu: {
    inReview: "In review…",
    onHold: "On hold…",
    inReviewBlocked: "Every account must be reconciled first",
  },
  handoffToTax: "Handoff to tax…",
  handoffDisabled: "Available after the December close locks",
  notStarted: "Not started",
  running: "Running…",
  decision: {
    question_id: "close-treatment-square-0831",
    n: 1,
    m: 1,
    steps: [
      {
        q: "How should the Aug 31 Square transfer of $6,412.40 be treated?",
        preselect: "deposit_in_transit",
        options: [
          {
            key: "deposit_in_transit",
            title: "Deposit in transit — it reached Front Range Bank on Sep 1",
            detail: "Matches the bank feed · Recommended",
          },
          { key: "record_in_september", title: "Record in September" },
          { key: "ask_client", title: "Ask Ben Ashby" },
        ],
      },
    ],
    skipText: "Skip",
  },
} as const;

/** "6 of 9 complete". */
export function progressWords(done: number, total: number): string {
  return `${String(done)} of ${String(total)} complete`;
}

/** "9 of 9 tasks · 7 open issues · finished 9:40 AM". */
export function completeWords(total: number, open: number, finished: string): string {
  const issues = `${String(open)} open ${open === 1 ? "issue" : "issues"}`;
  return `${String(total)} of ${String(total)} tasks · ${issues} · finished ${finished}`;
}

/** "Ready to run 22 tasks · 0 of 8 requests received · requests publish Oct 1 (BD1)". */
export function idleWords(ready: number, received: number, requests: number, bd1: string): string {
  return `Ready to run ${String(ready)} tasks · ${String(received)} of ${String(requests)} requests received · requests publish ${bd1} (BD1)`;
}
