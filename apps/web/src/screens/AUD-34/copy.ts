// AUD-34's words and figures, verbatim from the handoff (AUD-34 a to f; A-09 §3.5; SPEC-658 F5).
// Numbers are the handoff's (§9.2.5: coverage 78%, never 83%); no "$" in the table.
export const COPY = {
  title: "Group scoping & component materiality",
  proposed: "Proposed · OH",
  decidedPill: "Decided",
  edit: "Edit",
  signOff: "Sign off…",
  sourceDocs: "Source Docs",
  segments: ["Components", "Coverage", "Aggregation"] as const,
  basis: "AU-C 600 (SAS 149) · consolidated interim 8/31/2026 · management's FY2026 forecast",
  openInExcel: "Open in Excel",
  tallies: {
    groupMateriality: "GROUP MATERIALITY",
    pending: "Pending",
    recommended: "RECOMMENDED",
    groupPm: "GROUP PM",
    ct: "CT",
    salesFull: "THIRD-PARTY SALES · FULL SCOPE",
    assetsFull: "TOTAL ASSETS · FULL SCOPE",
    specific: "SPECIFIC PROCEDURES",
    auditors: "COMPONENT AUDITORS",
  },
  question: "Which group materiality should this audit use?",
  reserved: "Reserved to Engagement Partner",
  options: [
    {
      key: "pbt_5",
      label: "5% of forecast income before taxes — $240,000",
      tag: "Recommended by Accrued Agent",
      note: "Group PM 75% $180,000 · CT 5% $12,000. Forecast FY2026 income before taxes 4,800,000; the 8-month consolidated interim shows 3,500,000 (no tax provision yet).",
    },
    {
      key: "pbt_4",
      label: "4% of forecast income before taxes — $192,000",
      tag: null,
      note: "Group PM 75% $144,000 · CT 5% $9,600. For a first-year group audit if the predecessor's file review (AU-C 510) raises concerns.",
    },
    {
      key: "other",
      label: "Another benchmark or rate…",
      tag: null,
      note: "Group PM, CT and every component PM recompute as you type.",
    },
  ],
  reasonPlaceholder: "Rationale (required for the file)",
  citations: [
    "AU-C 600 (SAS 149)",
    "AU-C 320",
    "Consolidated TB · interim 8/31",
    "FY2026 forecast · Graham Whitlock",
  ],
  requestAnalysis: "Request more analysis…",
  decide: "Decide",
  managerBanner: "Only the engagement partner can decide group materiality.",
  remind: "Remind Margaret",
  decidedLine:
    "✓ Decided by Margaret Okonkwo · Sep 14 3:40 PM · 5% of forecast income before taxes = $240,000",
  decidedRationale:
    "First-year group audit; forecast consistent with the interim results; predecessor's FY2025 opinion unmodified.",
  componentsHead: "Components · 5",
  proposedBy: "Proposed by Omar Haddad · 3:05 PM",
  columns: [
    "Component",
    "Level",
    "Planned work",
    "Performed by",
    "Third-party sales",
    "Total assets",
    "Component PM",
    "Of group PM",
  ],
  pendingTip:
    "Allocated from group PM 180,000, weighted by component risk — pending the partner's decision",
  draftInstructions: "Draft component instructions…",
  componentAuditorTag: "Component auditor",
  plannedWork: {
    full: "Full scope",
    specific: "Specific procedures",
    analytical: "Analytical only",
  },
  suggestion:
    "Suggested: specific procedures on PP&E, the mortgage note and intercompany rent — 17% of assets, no third-party revenue.",
  coverageHead: "Coverage of planned work",
  coverage: [
    {
      label: "Third-party net sales · 73,000,000",
      full: "100%",
      specific: null,
      analytical: null,
    },
    {
      label: "Total assets · 50,760,000 after eliminations",
      full: "78%",
      specific: "22%",
      analytical: "0%",
    },
  ],
  coverageNote: "Shares measured on the consolidated interim TB at 8/31/2026, after E1–E5.",
  aggregationHead: "Aggregation risk",
  aggregation:
    "Component PMs sum to 384,000, above group PM 180,000, as expected with four components. Each component PM is below group PM; Operating Co. is covered by group-level analytics; Pruett & Lang must report every misstatement above 12,000 (group CT). Allocation basis: instructions §4.",
  total: "Total",
} as const;

export interface ComponentRow {
  name: string;
  where: string;
  level: string;
  planned: "full" | "specific" | "analytical";
  areas: string | null;
  performedBy: string;
  componentAuditor: boolean;
  sales: string;
  assets: string;
  pm: string;
  ofGroup: string;
}

/** The handoff's five components (AUD-34 (2)), in its order. */
export const COMPONENTS: readonly ComponentRow[] = [
  {
    name: "Harlow & Pike Manufacturing, LLC",
    where: "Dayton, OH",
    level: "3",
    planned: "full",
    areas: null,
    performedBy: "Group team",
    componentAuditor: false,
    sales: "57.5%",
    assets: "53%",
    pm: "135,000",
    ofGroup: "75%",
  },
  {
    name: "Harlow & Pike Distribution, Inc.",
    where: "Houston, TX",
    level: "3",
    planned: "full",
    areas: null,
    performedBy: "Pruett & Lang LLP",
    componentAuditor: true,
    sales: "42.5%",
    assets: "25%",
    pm: "105,000",
    ofGroup: "58%",
  },
  {
    name: "H&P Real Estate, LLC",
    where: "Dayton, OH",
    level: "2",
    planned: "specific",
    areas: "PP&E, mortgage note, intercompany rent",
    performedBy: "Group team",
    componentAuditor: false,
    sales: "—",
    assets: "17%",
    pm: "54,000",
    ofGroup: "30%",
  },
  {
    name: "Harlow & Pike Holdings, Inc.",
    where: "Chicago, IL",
    level: "1",
    planned: "specific",
    areas: "Term loan, corporate expenses, consolidation",
    performedBy: "Group team",
    componentAuditor: false,
    sales: "—",
    assets: "5%",
    pm: "90,000",
    ofGroup: "50%",
  },
  {
    name: "Harlow & Pike Operating Co.",
    where: "Chicago, IL",
    level: "2",
    planned: "analytical",
    areas: "Analytical procedures at group level",
    performedBy: "Group team",
    componentAuditor: false,
    sales: "—",
    assets: "—",
    pm: "—",
    ofGroup: "—",
  },
] as const; // fmt
