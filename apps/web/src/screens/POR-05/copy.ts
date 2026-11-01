// POR-05 copy, verbatim from the handoff (screens/POR-05 spec.md). Portal copy never says
// "Accrued" (DEC-01, ADR-133); the firm is named by the scope's branding.

export const COPY = {
  active: "Questions",
  title: "Questions",
  answered: (n: number, total: number) => `${String(n)} of ${String(total)} answered`,
  saved: (time: string) => `Saved automatically · ${time}`,
  teamRow: "Questions from your team",
  sections: "Sections",
  filter: { label: "Show", unanswered: "Unanswered", all: "All", answered: "Answered" },
  markDone: "✓ Mark as Done",
  yes: "Yes",
  no: "No",
  from: (name: string, on: string) => `From ${name} · ${on}`,
  upload1099: "Upload Form 1099-DA or your exchange's 2025 gains and losses report",
  uploadLink: "Upload…",
  uploaded: (file: string, size: string) => `${file} · ${size}`,
  youUploaded: "✓ You uploaded Sep 14",
  amounts: ["Traditional IRA", "Roth IRA", "HSA", "529 plan (New York)"] as const,
  answeredBand: (n: number) => `Answered (${String(n)})`,
  complete: "Thanks — Kevin Osei has your answers.",
  addressedToYou: "Addressed to you",
  dueOn: (on: string) => `Due ${on}`,
  // INV-4: the firm is the portal's own brand, never a name in the bundle (T-02 portal build).
  onlyTeam: (firm: string) => `Your answers go only to the ${firm} audit team.`,
  submit: "Submit answers",
  analyticsFrom: (firm: string) => `From ${firm}`,
  attach: "Attach a file (optional)",
  empty: "No questions right now.",
  emptyBody: (firm: string) => `${firm} will add questions here when they need your input.`,
  next: "Next question",
  reloaded: "This answer changed on another device. We reloaded it.",
} as const;
