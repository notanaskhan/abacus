// NOT-02 · Notice workspace (N-04-T14): every word verbatim from the handoff spec and
// docs/screens/NOT-02.md. Figures are the server's (AnalysisOut, NoticeOut); the copy frames them.

export const COPY = {
  back: "‹ All Notices",
  title: (code: string, year: number, client: string) => `${code} · TY${String(year)} · ${client}`,
  respondBy: (on: string, days: number) => `Respond by ${on} · ${String(days)} days`,
  status: {
    received: "Received",
    classified: "Classified",
    analyzing: "Analyzing",
    response_drafted: "Response drafted",
    approved: "Approved",
    sent: "Sent",
    awaiting_irs: "Awaiting IRS",
    closed: "Closed",
    escalated: "Escalated",
  } as Record<string, string>,
  tabs: ["Analysis", "Response", "Activity"] as const,
  tabsLabel: "Notice workspace",
  viewer: { title: (agency: string, code: string, on: string) => `${agency} ${code} · ${on}` },
  analysis: {
    title: "Analysis",
    segments: ["Notice vs return", "Information returns", "Transcript"] as const,
    segmentsLabel: "Analysis view",
    columns: { line: "Line", asFiled: "As filed", irs: "IRS proposed", change: "Change" },
    infoReturns: "Information returns",
    notOnReturn: "Not on return",
    agree: "Agree",
    others: (n: number, forms: string) => `${String(n)} others agree (${forms})`,
    issuedAfter: "issued after filing",
    why: "Why This Was Surfaced",
    off: "Agent analysis is off for this firm",
    running: "Comparing information returns with the return…",
    noTranscript: "No transcript rows yet.",
  },
  action: {
    proposed: "Proposed action",
    recommends: (position: string) => `Accrued Agent recommends: ${position}`,
    documents: (docs: number, cites: number) =>
      `${String(docs)} ${docs === 1 ? "document" : "documents"} · ${String(cites)} ${cites === 1 ? "citation" : "citations"}`,
    jump: (label: string) => `Open ${label}`,
    draft: "Draft response",
    start: "Start",
  },
  position: {
    agree: "Agree",
    partially_agree: "Partially agree",
    disagree: "Disagree",
  } as Record<string, string>,
  decision: {
    recommended: "Recommended by Accrued Agent",
    reasonField: "Rationale",
    decide: "Decide",
    reserved: (who: string) =>
      `Reserved to ${who} (signing partner). Sent to their Approvals queue.`,
    decided: (option: string, who: string, at: string) => `${option} · decided by ${who} · ${at}`,
  },
  authorization: {
    title: "Authorization",
    none: "None on file",
    note: "An 8821 lets us receive the notice, not represent. The taxpayers sign the response.",
    draft2848: "Draft Form 2848…",
  },
  activity: { title: "Activity", empty: "No activity yet." },
  states: { empty: "Notice not found." },
} as const;
