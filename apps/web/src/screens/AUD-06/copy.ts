// AUD-06 copy, verbatim from the handoff (spec.md, revision.md R2) and the A-02 epic (§3.1 caption,
// AC-4.1 tooltip, §2.1 empty state); docs/screens/AUD-06.md, Copy. Status words (layers, TB
// labels, tie / off) are the registry's; check labels, account names and figures are data.

export const COPY = {
  title: "Trial Balance",
  edit: "Edit",
  signOff: "Sign off…",
  sourceDocs: "Source Docs",
  /** The R2 label chip: "TB: Standard ⌄"; another label names its period, "TB: Interim ·
   * 8/31/2026" (revision.md g). */
  tbChip: (label: string, periodEnd?: string) =>
    periodEnd === undefined ? `TB: ${label}` : `TB: ${label} · ${periodEnd}`,
  /** g's one column: "Interim 8/31/2026". */
  labelColumn: (label: string, periodEnd: string) => `${label} ${periodEnd}`,
  /** AUD-06g's entity strip and its link (revision.md g; AUD-33 is planned). */
  entities: "Entity",
  consolidated: "Consolidated TB →",
  /** AUD-06h (revision.md h; AUD-38 is planned). */
  handOffToTax: "Hand off to tax…",
  /** The leadsheet's area picker (AUD-06e). */
  areas: "Audit area",
  tabs: { label: "Trial Balance view", trialBalance: "Trial Balance", leadsheets: "Leadsheets" },
  layers: "Layer",
  layerUnavailable: "Adjustments arrive with Findings & adjustments",
  openInExcel: "Open in Excel",
  checks: "Checks",
  columns: {
    description: "Description",
    boy: "Beginning of Year",
    eoy: "End of Year",
    aje: "AJE",
    wpRef: "WP Ref",
  },
  leadsheet: { account: "Fund", py: "PY", cy: "CY", change: "Δ", changePct: "Δ%" },
  /** "Imported by Simone Baptiste from a NetSuite export, Sep 11, 10:02 AM" (A-02 §3.1). */
  caption: (layer: string, name: string, source: string, at: string) =>
    `${layer}. Imported by ${name} from ${source}, ${at}.`,
  /** The provenance caption's source words, by snapshot source (A-02 §3.1, §4 T22). */
  sources: {
    import_netsuite_csv: "a NetSuite export",
    import_accrued_template: "the Accrued trial balance template",
  } as Readonly<Record<string, string>>,
  otherSource: "an import",
  /** The chip and tick popovers (spec INTERACTIONS). */
  signedOff: (name: string, level: string, at: string) =>
    `Signed off by ${name} · ${level} · ${at}`,
  levels: { 1: "Preparer (L1)", 2: "Reviewer (L2)" } as Readonly<Record<number, string>>,
  agreed: (name: string) => `Agreed · prepared by ${name}`,
  agentDraft: "Draft · Accrued Agent",
  doesNotTie: "Does not tie · linked to an issue",
  empty: "No trial balance yet",
  /** A-02-T24: the empty state's adoption (A-02 §3.1 AC-1). */
  adoptBody: "Adopt a pulled trial balance as this engagement's trial balance of record.",
  adopt: "Adopt as trial balance of record",
  snapshotChoice: "Pulled trial balance",
  snapshotOption: (period: string, source: string, at: string) =>
    `${period} · ${source} · pulled ${at}`,
  /** AC-7.1: "A newer trial balance is available · pulled 9:15 AM · 3 lines changed". */
  newer: (at: string, lines: number) =>
    `A newer trial balance is available · pulled ${at} · ${String(lines)} ${lines === 1 ? "line" : "lines"} changed`,
  useVersion: (n: number) => `Use v${String(n)}…`,
  reason: "Reason",
  adoptVersion: "Adopt",
  cancel: "Cancel",
  /** The source menu (A-02 §3.11, §3.12). */
  source: "Source",
  pullLatest: "Pull latest",
  askReconnect: "Ask client to reconnect",
  reconnectAsked: "Reconnect requested",
  pullStarted: "Pull started",
  failed: "That didn't work. Try again.",
  notFound: "This trial balance isn't available.",
  /** A-02-T35: a line's actions on P-04 fields (A-02 §3.6 AC-6.1, AC-6.2, AC-6.4). */
  lineActions: (account: string) => `Line actions for ${account}`,
  agreeToSource: "Agree to source…",
  markReviewed: "Mark reviewed (L2)",
  editLine: "Edit…",
  agreeTitle: (account: string) => `Agree ${account} to source`,
  agreeSearch: "Find in the source",
  agreeHit: (page: number) => `Page ${String(page)}`,
  agreeNoHits: "No match in this document.",
  agreeNoSource: "Open the source document in the viewer to agree this line.",
  agreeAction: "Agree",
  editTitle: (account: string) => `Edit ${account}`,
  wpRef: "WP ref",
  areaOverride: "Area",
  amountsLocked: "Amounts come from the ledger and can't be edited.",
  save: "Save",
} as const;
