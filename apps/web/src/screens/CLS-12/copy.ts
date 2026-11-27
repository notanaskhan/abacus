// CLS-12 copy (C-02-T48; handoff CLS-12 spec): words from the handoff; figures from the read.
export const COPY = {
  title: "Handoff to tax",
  handOff: "Hand off",
  close: "Close",
  source: "Source",
  target: "Target",
  carried: "Schedules carried",
  items: "Open tax-relevant items",
  keys: {
    close: "Close",
    tb: "Trial balance",
    balanced: "Balanced",
    entries: "Entries",
    ret: "Return",
    engine: "Engine",
    team: "Tax team",
    landsAs: "Lands as",
  },
  closeValue: (period: string, locked: string) => `${period} · Locked ${locked}`,
  tbValue: (version: string, year: number) => `${version} · year ended Dec 31, ${String(year)}`,
  balancedValue: "debits = credits",
  tie: "tie",
  entriesValue: "12 monthly batches carried as history (not re-posted)",
  returnValue: (form: string, year: number, client: string) =>
    `${String(year)} Form ${form} · ${client}`,
  teamValue: (preparer: string | null, reviewer: string | null) =>
    [
      preparer === null ? null : `${preparer} (preparer)`,
      reviewer === null ? null : `${reviewer} (reviewer)`,
    ]
      .filter((p) => p !== null)
      .join(" · "),
  landsAsValue: "UTB in Review › Financials, with a provenance banner",
  createIssue: "Create tax issue",
  note: "Tax-only entries (TJEs) stay in the tax workpapers and never post back to QuickBooks Online. Re-handing off after a reopen supersedes this TB and notifies the tax team.",
  schedule: {
    fixed_assets: (f: Record<string, string>) =>
      `cost ${f.cost ?? "—"} · accumulated depreciation ${f.accumulated_depreciation ?? "—"} · ${f.year ?? ""} book depreciation ${f.book_depreciation ?? "—"} → Fixed Assets`,
    prepaid_expenses: (f: Record<string, string>) =>
      `Cedar Mutual BOP fully amortized (${f.amortized ?? "—"}) · Dec 31 balance ${f.ending_balance ?? "—"} → no book-tax difference (12-month rule, Treas. Reg. §1.263(a)-4(f))`,
    deferred_revenue: () =>
      "subscriptions rollforward → advance-payment review (§451(c) one-year deferral; Schedule M-1 if book and tax differ)",
    shareholder_distributions: (f: Record<string, string>) =>
      `${f.total ?? "—"} → Schedule M-2 (AAA)`,
    accrued_liabilities: () => "→ Schedule M-1 review (shareholder-employee wages, see below)",
  } as Record<string, (f: Record<string, string>) => string>,
  handedOff: (form: string, year: number, issues: number) =>
    `Handed off to ${String(year)} Form ${form} · ${String(issues)} tax ${issues === 1 ? "issue" : "issues"} created`,
  banner: (locked: string, by: string, at: string) =>
    `TB from the December 2026 close, locked ${locked} · handed off by ${by} · ${at}`,
  viewClose: "View close ›",
  openIssues: "Open the tax issues (TXP-10) ›",
  preview: "TXP-02 provenance banner",
  superseded: (on: string, preparer: string | null, reviewer: string | null) =>
    `The December close was reopened on ${on}. Handing off again replaces TB v1 and notifies ${[preparer, reviewer].filter((p) => p !== null).join(" and ")}.`,
  notAvailable: "Not available yet",
  failedToLoad: "The hand-off could not load.",
  retry: "Retry",
};
