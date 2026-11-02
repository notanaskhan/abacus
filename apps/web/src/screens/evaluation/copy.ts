// The Evaluation chrome (A-06-T12; A-06 §5): the tab words of AUD-15, AUD-16 and AUD-17's bar,
// verbatim from the handoff.
export const COPY = {
  tabs: "Evaluation",
  findings: "Findings",
  misstatements: "Misstatements",
  reviewNotes: "Review notes",
  signOffs: "Sign-offs",
  fsDisclosure: "Financial statements",
  planned: "Not built yet",
  plannedBody: (screen: string): string => `Opens ${screen} once it is built.`,
  back: "Back",
} as const;
