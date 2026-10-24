// The audit cockpit L3's words (A-01-T06), verbatim from the AUD-02 and AUD-03 handoff (spec.md
// and revision.md; docs/screens/AUD-02.md Copy). Screens add their own copy in copy.ts; these are
// the strings the shared cockpit parts draw.

export const AUDIT_MESSAGES = {
  back: "All Audits",
  railTitle: "Overview",
  bands: {
    overview: "Overview",
    planning: "Planning",
    group: "Group",
    fieldwork: "Fieldwork",
    completion: "Completion",
    reporting: "Reporting",
  },
  started: (time: string) => `Started ${time}`,
  layout: "Layout",
  dock: { agent: "Agent", viewer: "Viewer" },
  aiUnavailable: "AI isn't available for real client data yet",
  blocked: {
    title: (person: string) => `Waiting on ${person}`,
    action: "Open decision",
    /** Announced while the decision card (SHL-11, P-04) is a planned link. */
    unavailable: "Not built yet",
  },
} as const;

export type BandKey = keyof typeof AUDIT_MESSAGES.bands;
