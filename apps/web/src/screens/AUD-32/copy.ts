// AUD-32 words, verbatim from the handoff (AUD-32 spec.md).
export const COPY = {
  title: "Consolidation setup",
  subtitle: "FY2026 Group Financial Statement Audit",
  close: "Close",
  steps: {
    details: { label: "Details", sub: "FY2026 group consolidation" },
    structure: {
      label: "Structure",
      sub: (n: number, tiers: number) => `${String(n)} entities · ${String(tiers)} tiers`,
    },
    trial_balances: {
      label: "Trial balances",
      sub: (done: number, all: number) => `${String(done)} of ${String(all)} attached`,
    },
    review: { label: "Review", sub: "Finalize" },
  },
  note: "Trial balances are read-only snapshots of the ledger. Eliminations are added later in the consolidated TB and never change a snapshot.",
  tbTitle: "Trial balances",
  tbIntro:
    "Attach an interim and a prior trial balance to each entity. Pull them from the NetSuite connection, upload a file, or reuse a file already in this engagement's evidence.",
  search: "Search entities",
  labelFilter: "Label",
  pullAll: "Pull all from NetSuite…",
  bulk: "Bulk upload…",
  columns: ["Name", "Label", "Start", "End", "Period", "Total debits", "Status"],
  labels: {
    interim: "Interim",
    prior: "Prior",
    standard: "Standard",
    budget: "Budget",
    preliminary: "Preliminary",
  } as Record<string, string>,
  period: { current: "Current", prior: "Prior" } as Record<string, string>,
  parent: "Parent entity",
  owned: "100%",
  balanced: "Balanced",
  needsReauth: "Needs reauth",
  notNeeded: "Not needed",
  reauthHelp:
    "The NetSuite connection needs to be renewed by Nadine Brooks in the portal (POR-16).",
  requestReconnection: "Request reconnection…",
  noTb: "No trial balance added",
  add: "Add",
  addMenu: {
    upload: ["Upload trial balance…", "XLSX or CSV"],
    connection: ["From NetSuite connection", "Subsidiary 5 · period 12/2025"],
    evidence: ["From evidence", "A file already in this engagement"],
  },
  priorDash:
    "Prior balances support comparatives and opening-balance procedures (AU-C 510); open the snapshot to see lines.",
  source:
    "Source: NetSuite OneWorld · 5 subsidiaries · interim pulled 10:38 AM · USD only · every entity 100% owned (no noncontrolling interest, no translation).",
  back: "Back",
  next: "Next",
  nextReason: "Attach every trial balance, or mark one not needed with a reason",
  footer: (done: number, all: number, missing: readonly string[]) =>
    `${String(done)} of ${String(all)} trial balances attached${missing.length > 0 ? ` · missing: ${missing.join(", ")}` : ""}`,
  markNotNeeded: "Mark not needed…",
  reason: "Reason",
  confirmNotNeeded: "Mark not needed",
  details: {
    consolidation: "Consolidation",
    name: "Name",
    engagement: "Engagement",
    engagementValue: "A28 FY2026 Group Financial Statement Audit",
    yearEnd: "Year end",
    currency: "Reporting currency",
    periods: "Periods",
    interim: "Interim",
    interimValue: "8/31/2026 · 8 months",
    prior: "Prior",
    priorValue: "12/31/2025 · audited by Harrington Reese LLP",
    source: "Source",
    sourceValue: "NetSuite OneWorld · Harlow & Pike · connected, read-only",
    labels: "Labels",
    labelsValue: "Standard · Interim · Prior · Budget · Preliminary",
  },
  structure: {
    banner:
      "I proposed this structure from the 5 NetSuite OneWorld subsidiaries and the FY2025 component list attached at set-up: 3 tiers. Review it before saving.",
    use: "Use structure",
    edit: "Edit",
    addEntity: "Add entity",
  },
  review: {
    summary: (n: number, tiers: number, tbs: number) =>
      `${String(n)} entities · ${String(tiers)} tiers · ${String(tbs)} trial balances · all balanced`,
    columns: ["Entity", "Level", "Parent", "Interim total debits", "Prior", "Component auditor"],
    total: "Total",
    finalize: "Finalize",
    hint: "Finalizing needs a Manager. The TB mapper starts when the snapshots are saved.",
  },
  finalized: "Finalized",
  toast: "Consolidation finalized · 5 entities · trial balance mapping started",
  view: "View", // the toast's one action: opens AUD-33 (the handoff's AUD-32 → AUD-33 link)
} as const;
