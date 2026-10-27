// Ridgeline Property Partners, LP, 2025 Form 1065, at E0 (F-06-T02): the capital rollforward by
// partner for TPL-06 (as drafted and fixed), the tie-out to Schedule L, and the preparer memo
// for TPL-10, verbatim from the handoff (screens/TPL-06 and TPL-10 spec.md; the TPL-10 canvas
// `Wave 0 - Templates.dc.html#tpl10`). Every figure is a whole-dollar decimal string as the
// server would send it; totals are carried, never summed in the browser (ADR-050). The footing
// tests in __tests__/tax.foot.test.ts prove they foot.

export const RIDGELINE = "Ridgeline Property Partners, LP";
export const RIDGELINE_ENGINE_RETURN = "2025P:Ridgeline:V2";

export interface CapitalRow {
  partner: string;
  tag: "GP" | "LP";
  /** Interest 1/1–6/30 · 7/1–12/31 ("—" when the partner held none). */
  interest: readonly [string, string];
  beginning: string;
  contributions: string;
  income: string;
  taxExempt: string;
  transfers: string;
  distributions: string;
  endingDrafted: string;
  endingFixed: string;
}

export const CAPITAL_ROWS: readonly CapitalRow[] = [
  {
    partner: "Ridgeline GP LLC",
    tag: "GP",
    interest: ["2%", "2%"],
    beginning: "80000",
    contributions: "0",
    income: "25000",
    taxExempt: "124",
    transfers: "0",
    distributions: "-12000",
    endingDrafted: "93000",
    endingFixed: "93124",
  },
  {
    partner: "Meera Shah",
    tag: "LP",
    interest: ["38%", "38%"],
    beginning: "2280000",
    contributions: "0",
    income: "475000",
    taxExempt: "2356",
    transfers: "0",
    distributions: "-228000",
    endingDrafted: "2527000",
    endingFixed: "2529356",
  },
  {
    partner: "Pell Street Ventures LLC",
    tag: "LP",
    interest: ["35%", "30%"],
    beginning: "2100000",
    contributions: "0",
    income: "406250",
    taxExempt: "2015",
    transfers: "-331405",
    distributions: "-180000",
    endingDrafted: "1994845",
    endingFixed: "1996860",
  },
  {
    partner: "Pell Street II LLC",
    tag: "LP",
    interest: ["—", "5%"],
    beginning: "0",
    contributions: "0",
    income: "31250",
    taxExempt: "155",
    transfers: "331405",
    distributions: "-30000",
    endingDrafted: "332655",
    endingFixed: "332810",
  },
  {
    partner: "Jonah Feld",
    tag: "LP",
    interest: ["25%", "25%"],
    beginning: "1500000",
    contributions: "250000",
    income: "312500",
    taxExempt: "1550",
    transfers: "0",
    distributions: "-150000",
    endingDrafted: "1912500",
    endingFixed: "1914050",
  },
];

/** The Total row, as the server sends it. */
export const CAPITAL_TOTAL = {
  interest: "100%",
  beginning: "5960000",
  contributions: "250000",
  income: "1250000",
  taxExempt: "6200",
  transfers: "0",
  distributions: "-600000",
  endingDrafted: "6860000",
  endingFixed: "6866200",
} as const;

/** Tie-out to Schedule L (TPL-06a; the difference is "—" once fixed). */
export const TIE_OUT = {
  m2Drafted: "6860000",
  scheduleL: "6866200",
  differenceDrafted: "-6200",
  issueRef: "Issue 2",
} as const;

/** Pell Street II's capital: 5/35 of Pell Street Ventures' 6/30 capital (§706(d)). */
export const TRANSFER = {
  pellStreetJune30: "2319835",
  pieces: ["2100000", "218750", "1085"],
  points: 5,
  of: 35,
  capital: "331405",
  price: "360000",
  excess: "28595",
} as const;

export type TallyResult = "tie" | "off" | "pending";

export interface TallyItem {
  key: string;
  result?: TallyResult;
  /** "off 6,200": the difference the off pill shows. */
  difference?: string;
  value?: string;
}

export const TALLY_DRAFTED: readonly TallyItem[] = [
  { key: "capitalFoots", result: "tie" },
  { key: "m2Ties", result: "off", difference: "6200" },
  { key: "bookTies", result: "tie" },
  { key: "itemLDerives", result: "tie" },
  { key: "beginTotal", value: "5960000" },
  { key: "contributions", value: "250000" },
  { key: "cyIncome", value: "1250000" },
  { key: "transfers", value: "0" },
  { key: "distributions", value: "600000" },
  { key: "endTotal", value: "6860000" },
];

export const TALLY_FIXED: readonly TallyItem[] = TALLY_DRAFTED.map((t) =>
  t.key === "m2Ties"
    ? { key: t.key, result: "tie" }
    : t.key === "endTotal"
      ? { key: t.key, value: "6866200" }
      : t,
);

/** The open-issue count on the return at E0 (G-C02, DEC-801). */
export const RIDGELINE_OPEN_ISSUES = 11;

// --- the preparer memo (TPL-10) ------------------------------------------------------------------

export const MEMO_TITLE = "Ridgeline Property Partners, LP — 2025 Form 1065 preparer memo";

/** Book-to-tax bridge, whole dollars (the mini statement table). */
export const BRIDGE = {
  rents: "3776500",
  parking: "96400",
  rentalExpenses: "-2641300",
  netRental: "1231600",
  interest: "18400",
  taxExempt: "6200",
  bookNetIncome: "1256200",
} as const;

export const BRIDGE_LABELS: Readonly<Record<keyof typeof BRIDGE, string>> = {
  rents: "Rents",
  parking: "Parking & other property income",
  rentalExpenses: "Rental expenses",
  netRental: "Net rental real estate income",
  interest: "Interest income",
  taxExempt: "Tax-exempt interest",
  bookNetIncome: "Book net income",
};

export const DEPRECIATION = {
  total: "733500",
  parts: ["480000", "9500", "180000", "64000"],
} as const;

export const STATE_SHARES = {
  total: "1231600",
  parts: [
    { state: "Illinois", pct: "46.0%", amount: "566536" },
    { state: "Colorado", pct: "31.5%", amount: "387954" },
    { state: "New York", pct: "22.5%", amount: "277110" },
  ],
} as const;

/** Memo sections: heading, paragraphs and the citation each paragraph carries ([1]–[5]). */
export const MEMO_SECTIONS: readonly {
  heading: string;
  paragraphs: readonly string[];
  bullets?: readonly string[];
  cite?: number;
  table?: "bridge";
}[] = [
  {
    heading: "Facts",
    paragraphs: [
      "The partnership owns three rental properties: Elm Street (Chicago, commercial), Larimer Lofts (Denver, residential) and Bergen Street (Brooklyn, residential). Books are kept on the income-tax basis. Partners at year-end: Ridgeline GP LLC (GP, 2%), Meera Shah (38%), Pell Street Ventures LLC (30%), Pell Street II LLC (5%) and Jonah Feld (25%).",
    ],
    cite: 1,
  },
  {
    heading: "Structural events",
    paragraphs: [
      "On 6/30/2025 Pell Street Ventures LLC sold 5 points to Pell Street II LLC for $360,000. Items are allocated under §706(d) with the interim-closing method and a monthly convention. Pell Street II's capital is 5/35 of Pell Street Ventures' 6/30 capital of 2,319,835 (including 1,085 of first-half tax-exempt interest, per Reg. §1.704-1(b)(2)(iv)(l)) = 331,405; the 28,595 excess of price over capital (360,000 − 331,405) is held as a §743(b) placeholder pending the partners' §754 decision. Jonah Feld contributed 250,000 during 2025.",
    ],
    cite: 2,
  },
  {
    heading: "Book-to-tax bridge",
    table: "bridge",
    paragraphs: [
      "AJE-1 accrues the December real estate tax installment of 18,500. TJE-1 moves tax-exempt interest of 6,200 to Schedule K line 18A.",
    ],
    cite: 3,
  },
  {
    heading: "Depreciation",
    paragraphs: [
      "2025 depreciation is 733,500: buildings 480,000; Elm Street roof 9,500 (39-year, mid-month); Larimer parking lot 180,000 (15-year, 100% bonus, acquired after Jan 19, 2025); Bergen Street appliances 64,000 (5-year, 100% bonus).",
    ],
    cite: 4,
  },
  {
    heading: "States and PTET",
    paragraphs: [
      "Sourced by property: Illinois 46.0% (566,536), Colorado 31.5% (387,954), New York 22.5% (277,110). PTET elected in all three: IL 28,044 · CO 17,070 · NY 18,982, paid Mar 12, 2026 with the state extensions (no 2025 estimates were made), so the deduction falls in TY2026.",
    ],
    cite: 5,
  },
  {
    heading: "Distributions",
    paragraphs: ["One distribution of 600,000 on Dec 15, 2025, by year-end percentages."],
  },
  {
    heading: "Open items",
    paragraphs: [],
    bullets: [
      "Schedule M-2 is off 6,200 — tax-exempt interest is missing from the capital rollforward (review point).",
      "§754 decision outstanding (waiting on the client).",
      "K-1s are drafts, shared internally with the Feld and Shah 1040s; release follows partner approval.",
    ],
  },
  {
    heading: "Opportunities",
    paragraphs: [
      "A cost segregation study on Elm Street (in service Apr 2018, cost 6,240,000) could reclassify part of the building to shorter lives. Proposed as an advisory project.",
    ],
  },
];

/** The structure pane's KV rows (TPL-10 "Partnership › General Information"). */
export const GENERAL_INFORMATION: readonly { key: string; value: string; link?: boolean }[] = [
  { key: "status", value: "In review · Partner" },
  { key: "partnership", value: RIDGELINE },
  { key: "ein", value: "••-•••0287" },
  { key: "activity", value: "Rental real estate (3 properties)" },
  { key: "method", value: "Income-tax basis" },
  { key: "taxYear", value: "Calendar year 2025" },
  { key: "partners", value: "5 (1 GP · 4 LP)" },
  { key: "allocation", value: "Straight percentage · §706(d) interim closing" },
  { key: "extension", value: "Form 7004 filed Mar 12, 2026" },
  { key: "due", value: "Sep 15, 2026" },
  { key: "engineReturn", value: RIDGELINE_ENGINE_RETURN },
  { key: "client", value: RIDGELINE, link: true },
  { key: "engagement", value: "TY2025 Form 1065", link: true },
  { key: "binder", value: "2025 Binder", link: true },
  { key: "files", value: "2025 · Ridgeline", link: true },
  { key: "preparer", value: "Olivia Brandt" },
  { key: "reviewer", value: "Samuel Ito" },
  { key: "signer", value: "Daniel Reyes" },
  { key: "created", value: "Jun 2, 2026" },
];

export const MEMO_ADOPTED = { by: "Olivia Brandt", at: "2026-09-10" } as const;
export const MEMO_APPROVED = { by: "Samuel Ito", at: "2026-09-14T09:40:00-05:00" } as const;
