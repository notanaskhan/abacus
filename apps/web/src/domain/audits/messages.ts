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
  /** The Viewer tab (SHL-08 in the dock). Not drawn in any artboard (DEC-341). */
  viewer: {
    none: "Select a document to view it here",
    unavailable: "This document can't be shown here",
    /** The E5 kit's revealed-value note ("Revealed by Samuel Ito · 9:31 AM · logged to the audit
     * trail", F-05-T47). */
    revealed: (person: string, at: string) =>
      `Revealed by ${person} · ${at} · logged to the audit trail`,
    /** Not drawn (DEC-421): the toast rules' wording for a refused reveal. */
    revealFailed: "Couldn’t reveal the value",
    /** The shell's step-up words (shell/mfa.tsx `ConfirmItsYou`). */
    stepUp: {
      title: "Confirm it's you",
      body: "This action needs a recent sign-in. Sign in again, then try once more. If it still isn't allowed, your role doesn't permit it.",
      cancel: "Cancel",
      signIn: "Sign in again",
    },
  },
  /** The v1 Agent tab (DV-2; SPEC-027 words). */
  agent: {
    pause: "Pause agent",
    paused: (person: string) => `Paused by ${person}`,
    menu: "Agent actions",
    empty: "Nothing yet",
    emptyBody:
      "When the engagement agent screens, retrieves or suggests something, it shows here.",
  },
  blocked: {
    title: (person: string) => `Waiting on ${person}`,
    action: "Open decision",
    /** Announced while the decision card (SHL-11, P-04) is a planned link. */
    unavailable: "Not built yet",
  },
} as const;

export type BandKey = keyof typeof AUDIT_MESSAGES.bands;
