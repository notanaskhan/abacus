// AUD-38's words, verbatim from the handoff (screens/AUD-38 spec.md STATES and fieldsets). The
// figures and names come from the preview read; these are the labels and fixed sentences only.
export const COPY = {
  title: "Hand off to tax",
  handOff: "Hand off",
  source: {
    title: "Source",
    engagement: "Engagement",
    tb: "Trial balance",
    released: "Released",
    snapshot: "Snapshot",
    snapshotValue: "Locked at release · a later change creates a new version",
    balanced: "Balanced",
    balancedPill: "Balanced",
    book: "Book income",
    bookValue: (pretax: string, tax: string, net: string) =>
      `Income before taxes ${pretax} · tax expense ${tax} · net income ${net}`,
  },
  target: {
    title: "Target",
    return: "Return",
    engagement: "Engagement",
    engagementValue: (created: string, filed: string | null, due: string | null) =>
      [
        `Created ${created}`,
        filed === null ? null : `Form 7004 filed ${filed}`,
        due === null ? null : `due ${due}`,
      ]
        .filter((x): x is string => x !== null)
        .join(" · "),
    team: "Tax team",
    landsAs: "Lands as",
    landsAsValue: "Trial balance in the 1120 workpapers (TXP-13) with a provenance banner",
  },
  mapping: {
    title: (n: number) => `Tax-code mapping · ${String(n)} accounts`,
    priorYear: (n: number) => `${String(n)} from the prior-year return mapping`,
    suggested: (n: number) =>
      `${String(n)} suggested by Accrued Agent — they travel as suggestions; the tax team adopts them`,
    review: (n: number) => `${String(n)} need review`,
    sendBlank: "Send blank",
    useSuggestion: "Use suggestion",
    travelLabel: (account: string) => `How ${account} travels`,
    blankNote: (who: string) =>
      `Accounts sent blank arrive with an empty tax code and 'Needs review' for ${who}.`,
    viewAll: (n: number) => `View all ${String(n)} mappings ›`,
  },
  schedules: { title: "Schedules carried" },
  items: {
    title: "Tax-relevant items",
    createIssue: "Create tax issue",
  },
  independence: "Independence",
  note: "Tax-only entries (TJEs) stay in the tax workpapers and never change the audited TB or the client's ledger. If the audited TB changes after release (AUD-30), handing off again supersedes this version and notifies the tax team.",
  needsReview: (n: number) => `${String(n)} accounts need review before hand-off`,
  needsReviewTip: (n: number) =>
    `Choose how the ${String(n)} accounts travel: blank for the tax team, or with the suggestion`,
  notAvailable: "Available after the report is released (G8)",
  superseded: (on: string, team: string) =>
    `The audited TB changed after release (AUD-30). Handing off again replaces the ${on} version and notifies ${team}.`,
  toast: (target: string, issues: number, accounts: number) =>
    `Handed off to ${target} · ${String(issues)} tax issue${issues === 1 ? "" : "s"} created · ${String(accounts)} accounts for the tax team to map`,
  by: (who: string, at: string) => `by ${who} · ${at}`,
  m1Strip: (book: string, candidate: string | null) =>
    candidate === null
      ? `Book income ${book}`
      : `Book income ${book} · candidate deduction ${candidate}`,
  openTxp13: "Open in TXP-13",
  table: {
    title: "Tax-code mappings",
    account: "Account",
    balance: "Balance",
    taxCode: "Tax code",
    source: "Source",
    sources: {
      firm_mapping: "Prior-year",
      tb_mapper: "Suggested",
      person: "Suggested",
      blank: "Blank",
    } as Record<string, string>,
  },
  unavailable: "The hand-off preview is not available yet.",
  loading: "Loading the hand-off",
};
