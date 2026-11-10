// TAX-05 copy and the Feld review data the artboards draw (T-04-T21; handoff TAX-05 spec,
// verbatim). Figures foot: the matrix's box 2 is 307,900 = 141,634 + 96,989 + 69,277 (the seed's
// FIGURES), Item L 1,500,000 + 250,000 + 312,500 − 150,000 = 1,912,500, UBIA 3,938,000 = 25% ×
// 15,752,000. Review 37 = 41 − 4 approved at the manager level, then 36 (DF-34).

export type Frame = "a" | "b" | "c" | "d" | "e" | "f";
export const FRAMES: readonly Frame[] = ["a", "b", "c", "d", "e", "f"];

export interface TreeRow {
  key: string;
  title: string;
  tag?: string;
  approved?: boolean;
  flagged?: number;
}
export interface TreeGroup {
  head: string;
  subs: { head: string; rows: TreeRow[] }[];
}

export const TREE: readonly TreeGroup[] = [
  {
    head: "General",
    subs: [
      {
        head: "Basic Data",
        rows: [
          {
            key: "py",
            title: "Feld 2024 Form 1040 & IT-201 (prior year, from CCH Axcess)",
            approved: true,
          },
          { key: "el", title: "TY2025 engagement letter (signed Feb 2, 2026)" },
          {
            key: "7216",
            title: "§7216 consents — use · AI disclosure (2 forms, signed Feb 2, 2026)",
          },
          { key: "org", title: "2025 tax organizer — Claire Feld" },
        ],
      },
    ],
  },
  {
    head: "Income",
    subs: [
      {
        head: "Wages, Salaries and Tips (W-2)",
        rows: [
          { key: "w2", title: "2025 W-2 From Mercer Hill Health", tag: "Claire", approved: true },
        ],
      },
      {
        head: "Interest & Dividends (1099-INT, 1099-DIV)",
        rows: [
          {
            key: "halvard",
            title: "Halvard Securities 2025 Consolidated 1099",
            tag: "Acct ••3318",
            approved: true,
          },
        ],
      },
      {
        head: "Sch E, p 2 - Partnership Passthrough (K-1 1065)",
        rows: [
          {
            key: "k1",
            title: "Ridgeline Property Partners, LP 2025 K-1",
            tag: "Draft K-1 · pre-release",
            flagged: 1,
          },
          { key: "stmtA", title: "Ridgeline K-1 Statement A — §199A", tag: "Draft" },
          { key: "state", title: "Ridgeline state K-1 schedule — IL / CO / NY", tag: "Draft" },
          { key: "ptet", title: "Ridgeline PTET statement", tag: "Draft" },
        ],
      },
    ],
  },
  {
    head: "Deductions",
    subs: [
      {
        head: "Sch A - Itemized Deductions",
        rows: [
          { key: "1098", title: "2025 Form 1098 From Hudson Mutual Savings", approved: true },
        ],
      },
    ],
  },
];

export interface MatrixRow {
  label: string;
  cy: string;
  py: string;
  lit?: boolean;
  status?: boolean;
  note?: string;
}

export const MATRIX: readonly MatrixRow[] = [
  { label: "Entity Type", cy: "Partnership", py: "Partnership" },
  { label: "Taxpayer/Spouse/Joint", cy: "T", py: "T" },
  { label: "Passive/Nonpassive", cy: "Passive", py: "Passive" },
  {
    label: "K-1 status",
    cy: "Draft K-1 · pre-release",
    py: "Released Sep 13, 2025",
    status: true,
  },
  { label: "Net Rental Real Estate Income", cy: "$307,900", py: "$281,600" },
  { label: "Interest Income", cy: "$4,600", py: "$4,120", lit: true },
  { label: "Tax-Exempt Interest", cy: "$1,550", py: "$1,400" },
  { label: "Section 199A Qualified Business Income", cy: "$307,900", py: "$281,600" },
  { label: "Section 199A UBIA", cy: "$3,938,000", py: "$3,760,000" },
  { label: "Distributions — Cash", cy: "$150,000", py: "$140,000" },
  { label: "Beginning Capital Account", cy: "$1,500,000", py: "$1,352,880" },
  { label: "Capital Contributed", cy: "$250,000", py: "$0" },
  {
    label: "Ending Capital Account",
    cy: "$1,912,500",
    py: "$1,500,000",
    note: "Ridgeline M-2 is off 6,200 — Item L becomes 1,914,050",
  },
];

export const WORKSHEET_ROWS = [
  { label: "Net rental real estate income", value: "307,900", chips: ["✓ KO", "✓ OB"] },
  { label: "Interest income", value: "4,600", chips: ["✓ KO", "✓ OB"] },
  { label: "Tax-exempt interest", value: "1,550", chips: ["✓ KO", "✓ OB"] },
  { label: "Distributions", value: "150,000", chips: ["✓ KO", "✓ OB"] },
] as const;

export const COPY = {
  title: "2025 Form 1040",
  client: "Jonah & Claire Feld",
  state: "In review · Manager",
  tabs: (review: number | null) =>
    [
      "Overview",
      "Intake 2",
      review === null ? "Review" : `Review ${String(review)}`,
      "Issues 4",
      "Activity",
    ] as const,
  tree: "Review",
  viewer: "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
  sheetTabs: ["Worksheets", "Leadsheets", "2-Year Comparison"] as const,
  picker: "Sch E - K-1",
  entities: "K-1 Entities",
  entity: "RIDGELINE PROPERTY PARTNERS, LP",
  pyHead: "2024",
  worksheet: "Sch E p2 — Ridgeline",
  tsj: "T",
  approve: "✓ Approve Document",
  unapprove: "× Unapprove Document",
  issue: "⚑ Issue…",
  toast: "Approved for manager review · Samuel Ito",
  allApproved: "All 41 documents approved at manager level · Samuel Ito",
  requestFinal: "Request final approval…",
  draftBlocks: "Final approval waits on the released K-1 (Draft K-1 · pre-release)",
  flaggedIssue: "Source K-1 box 18A 'Tax-exempt interest' is not on the worksheet",
  provenance: "Updated Aug 25 by Accrued Agent, from Box 5 of the draft K-1",
  loading: "Loading the review…",
} as const;

export const REVIEW_BEFORE = 37;
export const REVIEW_AFTER = 36;
