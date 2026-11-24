// CLS-08's words, verbatim from the handoff (screens/CLS-08 spec.md, revision.md) and the status
// vocabulary. The lock and reopen confirms are C-02-T37's (DEC-5925): the handoff names the
// action ("Lock close" → Locked) and not the confirm's words.

/** "Tess Moreno and Ben Ashby"; three or more as "A, B and C". */
function names(list: readonly string[]): string {
  if (list.length <= 1) return list.join("");
  return `${list.slice(0, -1).join(", ")} and ${list.at(-1) ?? ""}`;
}

export const COPY = {
  crumb: "Close › Deliverables",
  title: "August 2026 statements",
  release: "Release to client…",
  regenerate: "Regenerate…",
  edit: "Edit",
  drafting: "Accrued Agent is assembling the package",
  watermark: "DRAFT",
  lockClose: "Lock close",
  sections: {
    balance_sheet: "Balance sheet — Aug 31, 2026",
    income_statement: "Income statement — August vs July 2026",
    cash_flows: "Statement of cash flows — year to date",
    reconciliation_summary: "Reconciliation summary",
    commentary: "Management commentary — from accepted flux",
  } as Record<string, string>,
  firmOnly: "Firm-only — never released",
  basis: {
    title: "Reporting basis (SSARS)",
    question: "Are these statements prepared as part of client accounting services?",
    yes: "Yes",
    no: "No",
    periodEnd: "Period end",
    adoption: "SSARS 27 early adoption",
    notAdopted: "Not adopted",
    route: "Route",
    legend: "Legend",
    report: "Report",
    none: "None",
    // G: the standalone route follows the engagement letter (ENG-04).
    legendOrReport: "Legend or report",
    perLetter: "Per the engagement letter",
    letter: "Engagement letter",
    openLetter: "Open letter",
    routes: {
      ar_c_70_preparation: "AR-C 70 preparation",
      cas_by_product: "CAS by-product · no SSARS report or legend",
      standalone_letter: "Standalone engagement — AR-C 70 / 80 / 90 per the engagement letter",
    } as Record<string, string>,
    legendEach: (legend: string): string => `"${legend}" on each page`,
  },
  preconditions: {
    title: "Preconditions",
    accounts_unreconciled: (done: number, of: number): string =>
      `${String(done)} of ${String(of)} accounts reconciled`,
    issues_open: (n: number): string => `${String(n)} open issues`,
    entries_unposted: "Entries not posted",
    allMet: "Every precondition is met",
  },
  status: {
    released: "Released Sep 14",
    approved: "Approved by client",
    locked: "Locked",
    // D: "Released by Priya Raman · 4:25 PM · Portal › Deliverables · approval requested from …"
    releasedLine: (by: string, at: string, asked: readonly string[]): string =>
      [
        `Released by ${by} · ${at} · Portal › Deliverables`,
        asked.length === 0 ? null : `approval requested from ${names(asked)}`,
      ]
        .filter((p) => p !== null)
        .join(" · "),
    // E: "Approved by Tess Moreno · Sep 15, 8:42 AM (POR-08) · released by Priya Raman · …"
    approvedLine: (by: string, at: string, releasedBy: string | null, releasedAt: string | null) =>
      [
        `Approved by ${by} · ${at} (POR-08)`,
        releasedBy === null || releasedAt === null
          ? null
          : `released by ${releasedBy} · ${releasedAt}`,
      ]
        .filter((p) => p !== null)
        .join(" · "),
  },
  release_band: {
    title: "Release",
    studioVersion: "Studio version",
    studioSynced: (v: number): string => `v${String(v)} · synced with this package`,
  },
  studio: {
    open: "Open in statements studio",
    view: "View in studio",
    hint: "Edit layout and commentary in the studio. Figures stay linked to the posted ledger.",
  },
  lock: {
    title: (period: string): string => `Lock the ${period} close?`,
    body: "The client approved the package. Locking sets the Accrued period lock: entries, reconciliations and the package stay as they are until a Partner reopens the close with a reason.",
    confirm: "Lock close",
    locked: "Close locked",
  },
  reopen: {
    open: "Reopen close…",
    title: (period: string): string => `Reopen the ${period} close?`,
    body: "Reopening lifts the period lock. A later hand-off to tax supersedes the one made from this close.",
    reason: "Reason",
    confirm: "Reopen close",
    cancel: "Cancel",
    reopened: "Close reopened",
  },
  failed: "That didn't go through. Try again.",
  statements: {
    company: "Copperleaf Coffee Roasters, Inc.",
    balanceSheet: "Balance Sheet",
    balanceSheetDate: "August 31, 2026",
    incomeStatement: "Income Statement",
    incomePeriod: "For the months ended August 31 and July 31, 2026",
    august: "August 2026",
    july: "July 2026",
    page: (n: number, of: number): string => `Page ${String(n)} of ${String(of)}`,
    commentary: "Management commentary",
    commentarySub: "For the month ended August 31, 2026",
  },
  commentaryEdit: {
    label: "Commentary",
    save: "Save commentary",
    cancel: "Cancel",
    locked: "Figures stay linked to the posted ledger.",
  },
} as const;
