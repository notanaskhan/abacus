// EBP-03 Eligibility testing: words verbatim from the handoff spec (A-05-T23).
export const COPY = {
  title: "Eligibility Testing",
  edit: "Edit",
  signOff: "Sign off…",
  sourceDocs: "Source Docs",
  adopt: "Adopt (L1)…",
  adoptFirst: "Adopt the testing before signing off",
  check: (initials: string) => `✓ ${initials}`,
  dual: "Dual-Source Data Verification Matrix",
  matrix: "Eligibility Testing Matrix",
  columns: {
    n: "#",
    participant: "Participant",
    census: "Name (Census)",
    hr: "Name (HR)",
    dob: "DOB",
    hire: "Hire",
    entry: "Entry",
    rate: "Rate 12/2025",
    result: "Result",
  },
  exception: "Exception",
  needsHuman: "Needs human",
  testing: "Testing",
  markNoEffect: "Mark no effect",
  computation: (
    eligible: string | null,
    entry: string,
    keystone: string | null,
    rule: { age: number; months: number } | null,
  ) =>
    [
      eligible === null || rule === null
        ? `Entry ${entry}`
        : `Eligible = later of age ${String(rule.age)} and hire + ${String(rule.months)} ${rule.months === 1 ? "month" : "months"} = ${eligible} → entry ${entry}`,
      keystone === null ? null : `Keystone entry date ${keystone} ✓`,
    ]
      .filter((p) => p !== null)
      .join("; "),
  entryRule: {
    unverified:
      "No entry dates yet. Minimum age, Service requirement and Entry dates must be verified on EBP-02 first.",
    unreadable:
      "No entry dates yet. The verified entry rule on EBP-02 isn't worded in a way Accrued can compute from, so a person works these out.",
  },
  exceptionsCard: (n: number) => `Exceptions · ${String(n)} in sample`,
  missed: (name: string, entry: string, deferral: string, match: string) =>
    `${name} — entry ${entry}; missed deferrals ${deferral}, missed QACA match ${match}`,
  raise: "Raise exception…",
  raised: "Draft finding recorded on the Findings register.",
  raiseFailed: "Couldn't record the finding. Try again.",
  // The handoff's AUD-15 draft finding (Flag → AUD-15).
  findingTitle: (n: number) =>
    `Missed deferral opportunities — auto-enrollment not applied (${String(n)} participants)`,
  flag: "Flag to a draft finding",
  // The handoff's provision cards (EBP-02's provisions, read here).
  enrollmentCard: "Auto-Enrollment Provisions",
  escalationCard: "Auto-Escalation Provisions",
  provisionColumns: ["Provision", "Plan Election", "Plan Doc Reference"],
  requestOptOut: "Request opt-out forms",
  citations: (n: number) => `Citations (${String(n)})`,
  procedures: "Procedures (1)",
  openRecord: (name: string) => `PayGrid New-Hire Record: ${name}`,
  empty: "No sample yet.",
  emptyBody: "The eligibility test reads A-03's approved sample.",
} as const;
