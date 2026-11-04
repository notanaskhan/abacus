// EBP-04 · Contributions & remittance timeliness (A-05-T31): verbatim from the handoff spec and
// docs/screens/EBP-04.md. Every figure is the server's; the copy frames them.

export const COPY = {
  title: "Contributions & Remittance",
  edit: "Edit",
  signOff: "Sign off…",
  sourceDocs: "Source Docs",
  tabs: ["Reconciliation", "Timeliness", "Testing"] as const,
  tabsLabel: "Contributions view",
  openInExcel: "Open in Excel",
  tally: {
    lateDeposits: "LATE DEPOSITS",
    late: (n: number) => `${String(n)} late`,
    lostEarnings: "LOST EARNINGS",
    receivable: "RECEIVABLE",
    pending: "Pending",
    tie: "tie",
  },
  cardA: "Payroll → trust → financial statements",
  cardB: (n: number) => `Remittance timeliness · ${String(n)} payrolls`,
  practice: (days: number, timely: number, n: number) =>
    `Established practice: ${String(days)} business days (${String(timely)} of ${String(n)}). DOL standard: as soon as reasonably segregable.`,
  daysLabel: (n: number) => `${String(n)} business days`,
  columns: {
    payDate: "Pay date",
    deferrals: "Deferrals",
    match: "Match",
    deposited: "Deposited",
    days: "Business days",
    result: "Result",
  },
  late: "Late",
  cardC: "Late deposit — lost earnings & Schedule H line 4a",
  kv: {
    principal: "Principal (participant deferrals only)",
    deposited: "Deposited",
    daysLate: "Days late",
    lostEarnings: "Lost earnings",
    correction: "Correction",
    form5330: "Form 5330",
  },
  correction: {
    found: "Pending — VFCP Self-Correction Component",
    pending_vfcp_scc: "Pending — VFCP Self-Correction Component",
    corrected: "Corrected — VFCP Self-Correction Component",
  } as Record<string, string>,
  form5330: {
    exposure: "Excise tax exposure unless PTE 2002-51 relief applies",
    not_required: "Not required — excise tax relieved under PTE 2002-51",
    filed: "Filed",
  } as Record<string, string>,
  note4a:
    "Report on line 4a, not on line 4d. The employer match is not a participant contribution.",
  raise: "Raise exception…",
  draft4a: "Draft 4a schedule",
  testing: "The deferral and match recalculation opens with A-05-T32.",
} as const;
