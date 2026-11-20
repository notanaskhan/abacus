// TPL-20 copy (F-08-T09; docs/screens/TPL-20.md; F-08 §2 row TPL-20 and §3 A). The handoff folder
// is not on this machine, so the words come from the F-08 epic and the T18 screen contract; column
// headers follow the seed's field order (TASK-8748 deviations).
export const COPY = {
  title: "T18 Sheet specimen · Granite Peak FY2026 · BH-FS-430",
  backLabel: "All Audits",
  context: "Granite Peak Outdoor Supply, Inc. · FY2026",
  state: { working: "In progress", signedOff: "Signed off" },
  columns: {
    key: "Key",
    vendor: "Vendor",
    paidOn: "Paid",
    amount: "Amount",
    invoiceOn: "Invoice date",
    servicePeriod: "Service period",
    recordedIn: "Recorded in",
    conclusion: "Conclusion",
  },
  agentColumn: "Unrecorded liabilities tester",
  conclusion: {
    properly_included: "Properly included",
    improperly_excluded: "Improperly excluded",
    properly_excluded: "Properly excluded",
  },
  views: { all: "All rows", exceptions: "Exceptions" },
  savedViews: ["Exceptions"],
  rail: { title: "Audit program", procedure: "BH-FS-430 Search for Unrecorded Liabilities" },
  presence: (name: string, row: string) => `${name} is editing ${row}`,
  evidence: (have: number, of: number) => `${String(have)} of ${String(of)} evidence`,
  screening: (vendor: string) => `Screening flag · ${vendor}`,
  adopted: (n: number) => `${String(n)} adopted`,
  drawer: {
    title: (key: string, vendor: string) => `${key} · ${vendor}`,
    suggested: "Suggested by Accrued Agent · not yet adopted",
    adopt: "Adopt",
    edit: "Edit",
    raise: "Raise exception…",
    expand: "Expand testing",
  },
  dock: { title: "Agents", run: "Unrecorded liabilities tester · auto-started by trigger" },
  citations: {
    posting: "NetSuite bill posting period",
    invoice: "Vendor invoice",
  },
} as const;
