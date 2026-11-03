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
  computation: (eligible: string | null, entry: string, keystone: string | null) =>
    [
      eligible === null
        ? `Entry ${entry}`
        : `Eligible = later of age 21 and hire + 3 months = ${eligible} → entry ${entry}`,
      keystone === null ? null : `Keystone entry date ${keystone} ✓`,
    ]
      .filter((p) => p !== null)
      .join("; "),
  exceptionsCard: (n: number) => `Exceptions · ${String(n)} in sample`,
  missed: (name: string, entry: string, deferral: string, match: string) =>
    `${name} — entry ${entry}; missed deferrals ${deferral}, missed QACA match ${match}`,
  raise: "Raise exception…",
  requestOptOut: "Request opt-out forms",
  citations: (n: number) => `Citations (${String(n)})`,
  procedures: "Procedures (1)",
  openRecord: (name: string) => `PayGrid New-Hire Record: ${name}`,
  empty: "No sample yet.",
  emptyBody: "The eligibility test reads A-03's approved sample.",
} as const;
