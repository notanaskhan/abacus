// AUD-07 · Materiality copy (A-04-T10): verbatim from the handoff (screens/AUD-07, spec.md and the
// R2 revision). Figures, names, benchmarks, factors and captions are server data; these are the
// words around them.

export const COPY = {
  title: "Materiality",
  status: {
    proposed: "Proposed",
    decided: "Decided",
    reassessed: "Reassessed at final",
    revised: "Revised",
    superseded: "Superseded",
    current: "Current",
  },
  version: (n: number, status: string): string => `Version ${String(n)} · ${status}`,
  actions: { edit: "Edit", sourceDocs: "Source Docs", signOff: "Sign off…" },
  card: {
    question: "?",
    reserved: "Reserved to Engagement Partner",
    rationaleLabel: "Rationale (required for the file)",
    requestMore: "Request more analysis…",
    requestPrefill: "Show me materiality on total contributions as a specific threshold",
    decide: "Decide",
    remind: (first: string): string => `Remind ${first}`,
    banner: "Only the engagement partner can decide materiality.",
    recommended: "Recommended by Accrued Agent",
    decidedLine: (who: string, when: string, what: string): string =>
      `Decided by ${who} · ${when} · ${what}`,
    citations: "Citations",
  },
  benchmarks: {
    title: (end: string): string => `Benchmarks — unadjusted at ${end}`,
    columns: (current: string, priors: readonly string[]): string[] => [
      "Benchmark",
      `${current} (unadj.)`,
      ...priors,
      "Firm range",
      "Low",
      "High",
      "Use",
    ],
    use: {
      overall: "Overall",
      specific: "Specific",
      considered_for_specific: "Considered for specific",
      not_used: "Not used",
    } as Record<string, string>,
    range: (low: string, high: string): string => `${low}%–${high}%`,
    used: (parts: readonly string[]): string =>
      `Overall materiality used: ${parts.join(" · ")} (final, audited).`,
    usedPart: (year: string, rate: string, overall: string): string =>
      `${year} ${rate}% = ${overall}`,
    sparkline: (label: string): string => `${label}, three years`,
  },
  thresholds: {
    title: "Thresholds",
    rate: "Rate",
    overall: "Overall materiality",
    pm: "Performance materiality",
    ct: "Clearly trivial",
    specific: "Specific materiality",
    none: "None set",
    up: (what: string): string => `Raise ${what}`,
    down: (what: string): string => `Lower ${what}`,
    outside: "Outside the firm's materiality policy.",
  },
  factors: { title: "Qualitative factors", applies: "Applies", notApplies: "Does not apply" },
  history: {
    title: "Version history",
    recommended: (rate: string): string => `${rate}% recommended`,
    shares: (pm: string, ct: string): string => `PM ${pm} · CT ${ct}`,
    noChange: "no change",
    revised: "revised",
  },
  reassessment: {
    title: "Reassessment at final",
    finalAmount: "Final net assets",
    atRate: (rate: string): string => `At ${rate}%`,
    difference: (v: number): string => `Difference from Version ${String(v)}`,
    noChange: (v: number, pm: string): string =>
      `No change. Version ${String(v)} thresholds stand; work performed at PM ${pm} remains appropriate.`,
    revised: "Revised. The thresholds changed; the workpapers below re-run at the new figures.",
    conclusion: "Conclusion",
  },
  impact: {
    title: "Workpapers to re-run",
    reasons: {
      cites_materiality: "Cites materiality",
      depends_on_step: "Depends on step 7",
    } as Record<string, string>,
  },
  dock: {
    waiting: (who: string, since: string): string => `Waiting on ${who} since ${since}`,
    decided: (who: string): string => `Materiality decided by ${who}.`,
  },
  states: { empty: "No materiality has been proposed for this audit yet." },
  toasts: {
    decided: "Materiality decided.",
    reminded: (who: string): string => `Reminded ${who}.`,
    requested: "Analysis requested.",
  },
} as const;
