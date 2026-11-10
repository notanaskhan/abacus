// TAX-04's words and figures, verbatim from the handoff (screens/TAX-04 spec.md; T-04 §1, the
// Aug 26 snapshot: Review 36, Issues 7). Fixture mode only (T-04-T13): the live review tree and
// regions read T-04-T05's workspace routes when they answer. Every figure is the book's (§9.4):
// 2b = 2,310 + 4,600 = 6,910; 3a 11,960; 3b 14,820.

export type Tax04Frame = "a" | "b" | "c" | "d" | "e";

export const COPY = {
  record: {
    title: "2025 Form 1040",
    context: "Jonah & Claire Feld",
    // "Draft" is the 1040 subbar label for Preparing.
    state: "Draft",
    syncDate: "Apr 14",
  },
  tabs: { label: "Return sections", review: 36, issues: 7, intake: 2 },
  tree: "Review",
  sheetTabs: ["Worksheets", "Leadsheets", "2-Year Comparison"] as const,
  picker: "Form 1040",
  approvedToast: "Approved Halvard Securities 2025 Consolidated 1099",
  mismatchHelper: "Resolve 1 mismatch to approve",
  menu: ["Download", "Open in Files"] as const,
  halvardFile: "Jonah_Feld_2025_1099_Composite_Halvard.pdf",
  k1File: "Ridgeline_2025_K1_JonahFeld_DRAFT.pdf",
  linked3b: { label: "Form 1040 · Line 3b", value: "14,820" },
  linked3a: { label: "Form 1040 · Line 3a", value: "11,960" },
  issueNote: "Opens TAX-06 · Return issues",
} as const;

export interface TreeGroup {
  id: string;
  label: string;
  subs: readonly { id: string; label: string; docs: readonly (readonly [string, string])[] }[];
}

/** The review tree (prepare preset): groups, sub-heads and document names as the handoff draws
 * them. `halvard` and `k1` carry pages here; the rest open their name over a blank page. */
export const TREE: readonly TreeGroup[] = [
  {
    id: "general",
    label: "General",
    subs: [
      {
        id: "basic",
        label: "Basic Data",
        docs: [
          ["py1040", "Feld 2024 Form 1040 & IT-201 (prior year, from CCH Axcess)"],
          ["engagement", "TY2025 Engagement Letter (signed Feb 2, 2026)"],
          ["c7216", "§7216 Consents — Use · AI Disclosure (signed Feb 2, 2026)"],
          ["organizer", "2025 Tax Organizer — Claire & Jonah Feld"],
        ],
      },
    ],
  },
  {
    id: "income",
    label: "Income",
    subs: [
      {
        id: "w2s",
        label: "Wages, Salaries and Tips (W-2)",
        docs: [["w2", "2025 W-2 From Mercer Hill Health [Claire]"]],
      },
      {
        id: "intdiv",
        label: "Interest & Dividends (1099-INT, 1099-DIV)",
        docs: [
          ["halvard", "Halvard Securities 2025 Consolidated 1099"],
          ["halvard-ye", "Halvard Securities 2025 Year-End Summary"],
        ],
      },
      {
        id: "sche",
        label: "Sch E, p 2 - Partnership Passthrough (K-1 1065)",
        docs: [["k1", "Ridgeline Property Partners, LP 2025 K-1 [Draft K-1 · pre-release]"]],
      },
    ],
  },
  {
    id: "deductions",
    label: "Deductions",
    subs: [
      {
        id: "scha",
        label: "Sch A - Itemized Deductions",
        docs: [
          ["m1098", "2025 Form 1098 From Hudson Mutual Savings (co-op loan)"],
          ["coop", "2025 Co-op Maintenance Statement"],
        ],
      },
    ],
  },
  {
    id: "payments",
    label: "Payments/Penalties/Estimates",
    subs: [
      {
        id: "pay",
        label: "Payments",
        docs: [["ext", "2025 Form 4868 & IT-370 Confirmations"]],
      },
    ],
  },
];

/** A leadsheet row: its label, the value (whole dollars), a number line (500) or a support row,
 * and the source region it ties to (by key). */
export interface LeadRow {
  id: string;
  label: string;
  value: string;
  line?: boolean;
  /** The open issue's flag (2a: box 18A is not on the worksheet). */
  flag?: boolean;
  ties?: "div1a" | "div1b" | "int1" | "k1box5";
}

export const CARDS: readonly { id: string; title: string; rows: readonly LeadRow[] }[] = [
  {
    id: "interest",
    title: "2. Interest",
    rows: [
      { id: "texempt-all", label: "Tax-exempt interest, all sources", value: "0", flag: true },
      { id: "2a", label: "2a. Tax-exempt interest", value: "0", line: true },
      {
        id: "int-halvard",
        label: "Taxable interest — Halvard Securities (1099-INT box 1)",
        value: "2310",
        ties: "int1",
      },
      {
        id: "int-k1",
        label: "Taxable interest — Ridgeline K-1 box 5",
        value: "4600",
        ties: "k1box5",
      },
      { id: "2b", label: "2b. Taxable interest", value: "6910", line: true },
    ],
  },
  {
    id: "dividends",
    title: "3. Dividends",
    rows: [
      { id: "qual-all", label: "Qualified dividends, all sources", value: "11960" },
      { id: "3a", label: "3a. Qualified dividends", value: "11960", line: true, ties: "div1b" },
      { id: "schb6", label: "Schedule B line 6 — ordinary dividends", value: "14820" },
      { id: "3b", label: "3b. Ordinary dividends", value: "14820", line: true, ties: "div1a" },
    ],
  },
  {
    id: "retirement",
    title: "4-6. Retirement and social security",
    rows: [
      { id: "4a", label: "4a. IRA distributions (gross)", value: "0", line: true },
      { id: "4b", label: "4b. IRA distributions (taxable amount)", value: "0", line: true },
      { id: "5a", label: "5a. Pensions and annuities (gross)", value: "0", line: true },
      { id: "5b", label: "5b. Pensions and annuities (taxable amount)", value: "0", line: true },
      { id: "6a", label: "6a. Social security benefits", value: "0", line: true },
      { id: "6b", label: "6b. Taxable amount", value: "0", line: true },
    ],
  },
];

/** The mismatch frame (c): the leadsheet reads 14,280 while the source says 14,820. */
export const MISMATCH_3B = "14280";

/** The regions on page 1, in page points (document content, the C4 locators of fixture mode). */
export const REGIONS = {
  div1a: {
    doc: "halvard",
    label: "1a- Total ordinary dividends 14,820.00",
    bbox: [294, 79, 441, 120],
  },
  div1b: {
    doc: "halvard",
    label: "1b- Qualified dividends 11,960.00",
    bbox: [294, 120, 441, 161],
  },
  int1: { doc: "halvard", label: "1- Interest income 2,310.00", bbox: [294, 420, 441, 461] },
  k1box5: { doc: "k1", label: "5 Interest income 4,600", bbox: [294, 350, 441, 370] },
  k1box18a: {
    doc: "k1",
    label: "18A Tax-exempt interest income 1,550",
    bbox: [294, 374, 441, 394],
  },
} as const;

/** The demo's order (MOTION): 1a at 700 ms, 1b at 1000 ms, 3b at 1950 ms, 3a at 2250 ms; the
 * static frame is the poster at 3600 ms; reduced motion lights it at once. */
export const DEMO_MS = {
  first: 700,
  second: 1000,
  third: 1950,
  fourth: 2250,
  poster: 3600,
} as const;
