// TPL-24's words, verbatim from the handoff (screens/TPL-24 spec.md). The figures are the seed's
// (fixtures/seed/granite-peak-fy2026-ap-leadsheet.ts); the firm's name is the seed firm's.
import { AP_LEADSHEET } from "../../../fixtures/seed/granite-peak-fy2026-ap-leadsheet";

export const C = {
  firm: "Brightwater Hale",
  contextExcel: "Granite Peak · FY2026 · AP leadsheet",
  contextWord: "Granite Peak · FY2026 · statements",
  excel: {
    tabs: ["File", "Home", "Insert", "Formulas", "Data", "Review", "View", "Accrued"],
    sheets: ["AP leadsheet", "SURL results", "Legend"],
  },
  grid: {
    company: "Granite Peak Outdoor Supply, Inc.",
    title: "Accounts payable — leadsheet · June 30, 2026",
    workItem:
      "Work item BH-FS-430 Search for unrecorded liabilities · FY2026 Financial Statement Audit",
    objective: "Objective",
    objectiveText: "Accounts payable is complete and exists at June 30, 2026.",
    procedures: "Procedures",
    proceduresText:
      "Agree to the trial balance, the AP aging and the freight accrual; search for unrecorded liabilities (BH-FS-430).",
    materiality: "Materiality",
    materialityText: "155,000 · PM 116,250 · CT 7,750",
    leadsheet: "Leadsheet",
    headers: ["Acct", "Account", "6/30/2025", "6/30/2026", "", "Ref", "Change", "%", "Source"],
    sourceAging: "AP aging",
    sourceFreight: "Freight accrual",
    total: "Accounts payable",
    tieOut: "Tie-out",
    perTb: "Per trial balance, accounts 2010 and 2040",
    perLeadsheet: "Per leadsheet (D14)",
    difference: "Difference",
    surl: "Search for unrecorded liabilities (BH-FS-430)",
    payments: "Payments Jul 1 – Sep 18, 2026 (1,912)",
    tested: "Tested: 24 payments ≥ 50,000 + 16 random",
    excluded: "Improperly excluded · Front Range Freight Co. FRF-30418",
    belowPm: "Below PM 116,250",
    legend:
      "Tickmarks: ✓ Agreed to source · ⊕ Footed · ∧ Cross-footed · ◊ Traced to TB · ¢ Recalculated",
  },
  link: {
    cell: (cell: string) => `Cell ${cell}`,
    evidence: (file: string, page: number) => `Evidence: ${file} p.${String(page)}`,
    linkedBy: "Linked by Cole Hart · 2:12 PM · evidence v1",
    viewer: "Open in viewer ↗",
    unlink: "Unlink",
    selectTitle: "Link selection to evidence",
    search: "Search evidence in this engagement",
    files: [
      { name: "AP aging 6/30/2026.xlsx", meta: "Linked to D14" },
      { name: "Freight and duties accrual 6/30/2026.xlsx", meta: "Request · Received ✓" },
      { name: "Front Range Freight Co. — FRF-30418.pdf", meta: "SURL support · Received ✓" },
      { name: "Disbursements Jul 1 – Sep 18, 2026", meta: "NetSuite · 1,912 payments" },
    ],
    helper: "D14 is linked. Unlink it to choose other evidence.",
    workbook: (n: number) => `Links in this workbook · ${String(n)}`,
  },
  tickmarks: {
    title: "Standard set",
    meta: "Firm standard · 5 marks",
    labels: ["Agreed to source", "Footed", "Cross-footed", "Traced to TB", "Recalculated"],
    apply: "Apply to selection",
    legend: "Insert legend on sheet",
  },
  signOff: {
    title: "Workbook sign-offs · BH-FS-430 Search for unrecorded liabilities",
    preparer: "Preparer",
    reviewer: "Reviewer",
    signedBy: "Cole Hart · Sep 30, 2:21 PM",
    awaiting: "Awaiting Hannah Leclerc",
    board: "Board: BH-FS-430 moved to In review.",
    note: "Signing here records the same sign-off as in Accrued. Any later edit to the workbook marks it stale.",
  },
  changes: {
    title: (n: number) => `${String(n)} cells changed since sign-off`,
    signedBy: "Signed by Cole Hart · 2:21 PM",
    edited: "Reference edited by Cole Hart · 2:40 PM",
    show: "Show cell",
    review: "Review changes",
    again: "Sign off again…",
  },
  offline: {
    queued: (n: number) => `${String(n)} changes waiting to sync`,
  },
  word: {
    file: "Granite Peak FY2026 statements.docx",
    tabs: ["File", "Home", "Insert", "Layout", "Review", "View", "Accrued"],
    page: "Balance Sheets",
    lines: AP_LEADSHEET.wordIncoming.map((w, i) => ({
      label: w.label,
      value: w.old,
      changed: i === 0,
    })),
    incoming: (n: number) => `Incoming changes (${String(n)})`,
    update: "Update document",
    history: "Change history ›",
  },
  signedOut: {
    title: "Sign in to Accrued",
    body: "Use your firm's single sign-on. Links, tickmarks and sign-offs stay with the workpaper.",
    sso: (firm: string) => `Sign in with ${firm} SSO`,
  },
};
