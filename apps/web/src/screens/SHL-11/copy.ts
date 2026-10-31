// SHL-11 · Decision card copy (P-04-T50): verbatim from the handoff (screens/SHL-11, spec.md). The
// question, context, options, factors, figures and note are server data; these are the words
// around them.

export const COPY = {
  title: (kind: string): string => `Decision · ${kindLabel(kind)}`,
  proposed: (v: number, at: string): string => `v${String(v)} proposed ${at}`,
  question: "?",
  roles: {
    engagement_partner: "Engagement Partner",
    signer: "Tax Partner",
    partner: "Partner",
    manager: "Manager",
  } as Record<string, string>,
  reserved: (role: string, name: string, blocking: number): string =>
    blocking > 0
      ? `Reserved to ${role} · ${name} · blocking ${String(blocking)} ${blocking === 1 ? "workpaper" : "workpapers"}`
      : `Reserved to ${role} · ${name}`,
  recommended: "Recommended by Accrued Agent",
  factors: "Qualitative factors",
  notApplicable: "Not applicable",
  citations: (n: number): string => (n === 1 ? "1 citation" : `${String(n)} citations`),
  rationaleLabel: "Rationale (required)",
  requestMore: "Request more analysis…",
  requestPrefill: "Before I decide, show…",
  decide: "Decide",
  decideNote:
    "Deciding stamps your name and time, records v2 and unblocks the run. Gate G4 also needs the risk assessment reviewed.",
  waiting: (name: string, at: string): string => `Waiting on ${name} · requested ${at}`,
  notify: (first: string): string => `Notify ${first}`,
  decided: "Decided",
  decidedLine: (name: string, at: string, v: number, summary: string): string =>
    `${name} · ${at} · v${String(v)}: ${summary}`,
  viewHistory: "View history",
  superseded: (v: number): string => `Superseded by v${String(v)}`,
  history: {
    title: "History",
    proposed: (v: number, at: string): string =>
      `v${String(v)} · proposed by Accrued Agent · ${at}`,
    decided: (v: number, who: string, at: string, summary: string): string =>
      `v${String(v)} · decided by ${who} · ${at}${summary === "" ? "" : ` · ${summary}`}`,
    reassessed: (v: number, benchmark: string, summary: string, difference: string): string =>
      `v${String(v)} · reassessed at final on ${benchmark}: ${summary} — difference ${difference}, no change`,
    pills: { proposed: "Proposed", decided: "Decided", noChange: "No change", changed: "Changed" },
  },
  toasts: {
    decided: (kind: string, v: number): string =>
      kind === "planning_materiality"
        ? `Materiality v${String(v)} recorded · run resumed`
        : "Decision recorded",
    notified: (name: string): string => `${name} notified`,
    requested: "Analysis requested",
    failed: "The decision wasn't recorded. Try again.",
  },
  loading: "Loading the decision…",
  missing: "This decision can't be loaded.",
} as const;

function kindLabel(kind: string): string {
  return COPY_KINDS[kind] ?? "Decision";
}

const COPY_KINDS: Record<string, string> = {
  planning_materiality: "Planning materiality",
  deficiency_severity: "Deficiency severity",
  section_754: "§754 recommendation",
};
