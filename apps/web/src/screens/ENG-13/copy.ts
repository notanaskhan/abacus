// ENG-13 · Roll forward: every visible string, verbatim from the handoff spec and the screen
// contract (docs/screens/ENG-13.md, Copy). Names, counts and periods are data.

export type StepCode = "source" | "carry" | "template" | "team" | "review";
export type CarryCode = "team" | "template" | "request_list" | "prior_year_notes";

export const COPY = {
  title: "Roll forward",
  saved: (at: string) => `Draft · saved ${at}`,
  none: "—",
  steps: {
    source: "Source",
    carry: "What to carry",
    template: "Template version",
    team: "Team",
    review: "Review",
  } satisfies Record<StepCode, string>,
  toggle: { carry: "Carry", skip: "Skip" },
  toggleLabel: (row: string) => `Carry or skip ${row}`,
  gates: {
    released: (status: string) => `Source released · ${status}`,
    g1: "G1 Continuance — opened at Create",
    g2: "G2 Team independence — step 4",
    g3: "G3 Letter signed — after Create",
  },
  carrying: {
    title: "Carrying",
    people: (n: number) => `${String(n)} ${n === 1 ? "person" : "people"}`,
    requests: (n: number) => `${String(n)} requests as Draft`,
    template: (name: string, version: number) => `${name} v${String(version)}`,
    noTemplate: "No template",
    notes: "Prior-year notes linked",
    evidence: (n: number) => `${String(n)} evidence copied`,
  },
  source: {
    card: "Source",
    target: "Next year",
    engagement: "Engagement",
    status: "Status",
    period: "Period",
    name: "Name",
    newPeriod: "Period",
  },
  carry: {
    title: (name: string, period: string) => `What to carry into ${name} · ${period}`,
    from: (name: string, period: string, status: string) => `From ${name} · ${period} · ${status}`,
    card: "Engagement",
    rows: {
      team: "Team",
      template: "Template version",
      request_list: "Request list",
      prior_year_notes: "Prior-year notes",
    } satisfies Record<CarryCode, string>,
    detail: {
      team: (n: number) => `${String(n)} people · roles as last year; independence asked again`,
      template: (name: string, version: number) =>
        `${name} v${String(version)} · pinned at Create`,
      noTemplate: "No template on last year's engagement",
      requests: (n: number) => `${String(n)}, as Draft; the client sees nothing until you send`,
      notes: "Last year's record, letters and archive, linked read-only",
    },
    note: "Prior-year evidence stays in the archive and is referenced, never copied. The new engagement starts with no evidence, results or sign-offs.",
    archived: "The archive is locked; its evidence is referenced read-only.",
  },
  template: {
    card: "Template",
    current: "Current",
    pinned: "No newer version · pinned at Create",
    newer: (from: number, to: number) =>
      `v${String(from)} → v${String(to)} · the newer version is pinned at Create`,
    changes: "What changes",
    nothing: "Nothing to reconcile.",
    none: "Last year's engagement has no template; Create pins none.",
    signedNever: "Signed-off FY2026 work is never changed.",
  },
  team: {
    card: "Team",
    unavailable: "Not available",
    requested: "Independence requested at Create",
    roles: {
      engagement_partner: "Engagement partner",
      manager: "Manager",
      senior: "Senior",
      staff: "Staff",
      reviewer: "Reviewer",
      eqr_reviewer: "EQR reviewer",
      specialist: "Specialist",
    } as Readonly<Record<string, string>>,
  },
  review: {
    source: "Source",
    carry: "Carry",
    template: "Template",
    team: "Team",
    skipped: "Skipped",
  },
  saveDraft: "Save draft",
  create: "Create",
  createLetter: "Create & draft letter",
  createLetterHint: "Opens ENG-04 once N-02 lands",
  toast: {
    created: (name: string, period: string) => `Engagement created · ${name} · ${period}`,
    failed: "Couldn't save the draft. Try again.",
    createFailed: "Couldn't create the engagement. Try again.",
    notReleased: "Last year's engagement is not delivered or archived yet.",
  },
  discard: {
    title: "Discard this draft?",
    discard: "Discard",
    keep: "Keep editing",
  },
} as const;
