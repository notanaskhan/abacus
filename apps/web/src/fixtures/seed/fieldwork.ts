// A-08's typed fixture records for the stub contracts (A-08-T05; SPEC-657 AC-0.4, AC-0.5), typed
// with the generated shapes. Figures are the handoff's (AUD-12, AUD-13, AUD-14, AUD-26, POR-17
// spec.md) and the backend's `assurance/fieldwork_fixtures.py`, which computes every derived figure;
// nothing here is summed (the contract test foots them). The live values come from the
// Brightwater Hale scenario (A-08-T08) once the services land.
import type {
  ConfirmationCoverageOut,
  AnalyticsLineOut,
  CriterionOut,
  RespondentViewOut,
  TalliesOut,
} from "@abacus/api-client";

const criterion = (
  position: number,
  key: CriterionOut["key"],
  hits: number,
  params: Record<string, string> = {},
): CriterionOut => ({
  position,
  key,
  params,
  availability: "available",
  missing_fields: [],
  hit_count: hits,
});

/** AUD-12 a: Granite Peak's five risk criteria (firm policy content) and the unique count. */
export const GRANITE_PEAK_CRITERIA: CriterionOut[] = [
  criterion(1, "weekend_holiday", 142, { holiday_set: "legal_holidays" }),
  criterion(2, "round_amount", 38, { at_least: "50000.00" }),
  criterion(3, "post_close", 61, { through: "2026-07-15" }),
  criterion(4, "manual_by_role", 17, { role_class: "senior_management" }),
  criterion(5, "keywords", 9, { words: "plug, adjust" }),
];
export const GRANITE_PEAK_UNIQUE_FLAGGED = 236;

type Row = [caption: string, cy: string, py: string, change: string, pct: string, over: boolean];
const line = (
  position: number,
  group: string,
  [caption, cy, py, change, pct, over]: Row,
  status: AnalyticsLineOut["status"],
): AnalyticsLineOut => ({
  position,
  fs_line_key: caption.toLowerCase().replace(/[^a-z]+/gu, "_"),
  caption,
  group_key: group,
  cy,
  py,
  change,
  change_pct: pct,
  evaluated: true,
  over,
  derived: false,
  status,
  explanation: null,
  expectation: null,
});

/** AUD-13 a: the 14 evaluated lines (subtotals are derived and not listed). */
export const GRANITE_PEAK_LINES: AnalyticsLineOut[] = [
  line(
    1,
    "income_statement",
    ["Revenue", "48600000", "44900000", "3700000", "8.2", false],
    "within",
  ),
  line(
    2,
    "income_statement",
    ["Cost of goods sold", "29160000", "26490000", "2670000", "10.1", true],
    "unexplained",
  ),
  line(
    3,
    "income_statement",
    ["Operating expenses", "15820000", "14960000", "860000", "5.7", false],
    "within",
  ),
  line(
    4,
    "income_statement",
    ["Interest expense", "520000", "410000", "110000", "26.8", false],
    "within",
  ),
  line(5, "balance_sheet", ["Cash", "2140000", "2610000", "-470000", "-18.0", true], "explained"),
  line(
    6,
    "balance_sheet",
    ["Accounts receivable, net", "5860000", "4720000", "1140000", "24.2", true],
    "explained",
  ),
  line(
    7,
    "balance_sheet",
    ["Inventory, net", "11420000", "9180000", "2240000", "24.4", true],
    "unexplained",
  ),
  line(8, "balance_sheet", ["PP&E, net", "6380000", "6050000", "330000", "5.5", false], "within"),
  line(
    9,
    "balance_sheet",
    ["Other assets", "610000", "640000", "-30000", "-4.7", false],
    "within",
  ),
  line(
    10,
    "balance_sheet",
    ["Accounts payable", "4180000", "3310000", "870000", "26.3", true],
    "explained",
  ),
  line(
    11,
    "balance_sheet",
    ["Accrued liabilities", "1630000", "1540000", "90000", "5.8", false],
    "within",
  ),
  line(
    12,
    "balance_sheet",
    ["Revolver — Front Range Bank", "6500000", "4900000", "1600000", "32.7", true],
    "explained",
  ),
  line(
    13,
    "balance_sheet",
    ["Term loan", "3200000", "3800000", "-600000", "-15.8", true],
    "accepted",
  ),
  line(
    14,
    "balance_sheet",
    ["Stockholders' equity", "10900000", "9650000", "1250000", "13.0", true],
    "explained",
  ),
];
export const GRANITE_PEAK_TALLIES: TalliesOut = {
  lines: 14,
  over_threshold: 8,
  explained: 6,
  unexplained: 2,
  tb_balanced: true,
};

/** AUD-26 a: Lakeshore's revenue and expense lines (10% and $50,000). */
export const LAKESHORE_LINES: AnalyticsLineOut[] = [
  line(1, "revenue", ["Contributions", "2840000", "2610000", "230000", "8.8", false], "within"),
  line(2, "revenue", ["Grants", "1120000", "1480000", "-360000", "-24.3", true], "explained"),
  line(3, "revenue", ["Other revenue", "214000", "198000", "16000", "8.1", false], "within"),
  line(
    4,
    "expenses",
    ["Program services", "3210000", "3050000", "160000", "5.2", false],
    "within",
  ),
  line(
    5,
    "expenses",
    ["Management and general", "486000", "471000", "15000", "3.2", false],
    "within",
  ),
  line(6, "expenses", ["Fundraising", "318000", "342000", "-24000", "-7.0", false], "within"),
];

/** AUD-14: the coverage line, as the summary route answers it. */
export const GRANITE_PEAK_COVERAGE: ConfirmationCoverageOut = {
  population_total: "5860000.00",
  sent_total: "897950.00",
  sent_pct: "15.3",
  confirmed_total: "695200.00",
  differences_total: "4300.00",
  clearly_trivial: "7750.00",
};

/** POR-17 a: Summit Trail's page, one confirmation's render data only. */
export const POR17_SUMMIT_TRAIL: RespondentViewOut = {
  state: "open",
  request: {
    reference: "C2",
    type: "accounts_receivable",
    firm_name: "Brightwater Hale LLP",
    client_name: "Granite Peak Outdoor Supply, Inc.",
    respondent_org: "Summit Trail Outfitters",
    as_of: "2026-06-30",
    authorization_text:
      "Our auditors, Brightwater Hale LLP, are auditing our financial statements for the year ended June 30, 2026. Please confirm directly to them the balance you owed us at that date. This is not a request for payment.",
    authorized_by: "Luis Ferrante, Chief Financial Officer, Granite Peak Outdoor Supply, Inc.",
    authorized_on: "2026-09-18",
    balance_per_client: "412600.00",
    invoices: [
      { number: "INV-26-1841", invoice_date: "2026-05-28", amount: "138200.00" },
      { number: "INV-26-1907", invoice_date: "2026-06-12", amount: "151750.00" },
      { number: "INV-26-1966", invoice_date: "2026-06-26", amount: "122650.00" },
    ],
    client_accounts: [],
    list_every_account: false,
  },
  receipt: null,
  answered_on: null,
};

// ---- AUD-13 (A-08-T28): Granite Peak's analytics, verbatim from the handoff canvas (#aud13) ----

/** An explanation as the line shows it: the text and its one source chip. */
export interface AnalyticsNote {
  text: string;
  source: string;
}

/** a: the six over-threshold lines explained with evidence (the term loan already accepted). */
export const GRANITE_PEAK_EXPLANATIONS: Record<string, AnalyticsNote> = {
  cash: {
    text: "Revolver draws of 1,600,000 and cash funded the inventory build",
    source: "Front Range Bank statements Mar–Jun 2026",
  },
  accounts_receivable_net: {
    text: "Two new wholesale accounts: Summit Trail Outfitters 412,600, Canyon Basecamp Co. 198,450",
    source: "AR aging 6/30/2026",
  },
  accounts_payable: { text: "June receipts of fall inventory", source: "AP aging 6/30/2026" },
  revolver_front_range_bank: { text: "Draws Mar–Jun 2026", source: "Front Range Bank statements" },
  term_loan: { text: "Scheduled amortization 50,000 × 12", source: "Loan agreement §2.3" },
  stockholders_equity: {
    text: "Net income after tax 2,325,000 less dividends 1,075,000",
    source: "Board minutes Mar 12, 2026",
  },
};

/** a: the two over-threshold lines with no evidenced explanation (amber). */
export const GRANITE_PEAK_UNEXPLAINED: Record<string, string> = {
  cost_of_goods_sold:
    "Gross margin fell from 41.0% to 40.0%. No support found for freight or mix changes.",
  inventory_net: "No evidenced explanation",
};

/** c: the two plain questions for Luis Ferrante (firm template, editable; a person sends). */
export const GRANITE_PEAK_QUESTIONS: { line: string; movement: string; text: string }[] = [
  {
    line: "inventory_net",
    movement: "+2,240,000 · 24.4% over FY2025",
    text: "Inventory rose $2,240,000 (24.4%) to $11,420,000 at June 30, 2026. What drove the increase, and how much relates to products discontinued during the year?",
  },
  {
    line: "cost_of_goods_sold",
    movement: "+2,670,000 · 10.1% · gross margin 41.0% → 40.0%",
    text: "Gross margin fell from 41.0% to 40.0%. Which cost changes (freight, product mix, markdowns) explain it?",
  },
];

/** d: Luis Ferrante's answer on the inventory question (Sep 16). */
export const GRANITE_PEAK_CLIENT_ANSWER: AnalyticsNote = {
  text: "Fall stock received early for new wholesale orders (1,880,000); discontinued paddle-sports line still on hand (360,000)",
  source: "Client answer Sep 16 · Luis Ferrante",
};

/** b: the three runs (code tie-out, flux_explain, client questions drafted by code). */
export const GRANITE_PEAK_ANALYTICS_RUNS: string[] = [
  "Compare the trial balance to the ledger and source documents, and show what doesn’t tie",
  "Figure out why inventory changed from last year and trace it back to the source",
  "Draft client questions for unexplained movements",
];

/** e: the three recorded adjustments by line (C8 final layer); pre-tax income −114,480. */
export const GRANITE_PEAK_ADJUSTMENTS: Record<string, { amount: string; detail: string }> = {
  revenue: { amount: "-46200", detail: "AJE 2 (46,200) · Ridgeback Sports order shipped Jul 1" },
  cost_of_goods_sold: { amount: "68280", detail: "AJE 1 96,000 · AJE 2 (27,720)" },
  accounts_receivable_net: { amount: "-46200", detail: "AJE 2 (46,200)" },
  inventory_net: { amount: "-68280", detail: "AJE 1 (96,000) · AJE 2 27,720" },
  accrued_liabilities: { amount: "-28620", detail: "AJE 3 (28,620) · income tax payable" },
  stockholders_equity: {
    amount: "-85860",
    detail: "Pre-tax effect of AJEs 1–2 (114,480) · AJE 3 tax 28,620",
  },
};

/** e: adjusted FY2026 against audited FY2025, as the final layer answers it (all accepted). */
export const GRANITE_PEAK_FINAL_LINES: AnalyticsLineOut[] = GRANITE_PEAK_LINES.map((l) => {
  const FINAL: Record<string, [string, string, string]> = {
    revenue: ["48553800", "3653800", "8.1"],
    cost_of_goods_sold: ["29228280", "2738280", "10.3"],
    accounts_receivable_net: ["5813800", "1093800", "23.2"],
    inventory_net: ["11351720", "2171720", "23.7"],
    accrued_liabilities: ["1601380", "61380", "4.0"],
    stockholders_equity: ["10814140", "1164140", "12.1"],
  };
  const f = FINAL[l.fs_line_key];
  const moved = f === undefined ? l : { ...l, cy: f[0], change: f[1], change_pct: f[2] };
  return { ...moved, status: l.over ? "accepted" : "within" };
});

/** e: the final explanations (every over-threshold line accepted). */
export const GRANITE_PEAK_FINAL_EXPLANATIONS: Record<string, AnalyticsNote> = {
  cost_of_goods_sold: {
    text: "Margin 41.0% → 39.8% after adjustments: freight surcharges and lower-margin wholesale sales",
    source: "Client answer Sep 18 · Luis Ferrante",
  },
  cash: {
    text: "Revolver draws funded the inventory build",
    source: "Front Range Bank statements Mar–Jun 2026",
  },
  accounts_receivable_net: {
    text: "Two new wholesale accounts, less the Ridgeback Sports cutoff",
    source: "AR aging 6/30/2026",
  },
  inventory_net: {
    text: "Fall stock received early; discontinued paddle-sports line written down to NRV",
    source: "Client answer Sep 16 · Luis Ferrante",
  },
  accounts_payable: { text: "June receipts of fall inventory", source: "AP aging 6/30/2026" },
  revolver_front_range_bank: { text: "Draws Mar–Jun 2026", source: "Front Range Bank statements" },
  term_loan: { text: "Scheduled amortization 50,000 × 12", source: "Loan agreement §2.3" },
  stockholders_equity: {
    text: "Net income after tax 2,239,140 less dividends 1,075,000",
    source: "Board minutes Mar 12, 2026",
  },
};

/** The statement subtotals (derived, not evaluated): [after the line, caption, cy, py, change, %]. */
export const GRANITE_PEAK_SUBTOTALS: Record<
  "preliminary" | "final",
  {
    after: string;
    caption: string;
    cy: string;
    py: string;
    change: string;
    pct: string;
    total?: true;
  }[]
> = {
  preliminary: [
    {
      after: "cost_of_goods_sold",
      caption: "Gross profit",
      cy: "19440000",
      py: "18410000",
      change: "1030000",
      pct: "5.6",
    },
    {
      after: "interest_expense",
      caption: "Pre-tax income",
      cy: "3100000",
      py: "3040000",
      change: "60000",
      pct: "2.0",
    },
    {
      after: "other_assets",
      caption: "Total assets",
      cy: "26410000",
      py: "23200000",
      change: "3210000",
      pct: "13.8",
      total: true,
    },
    {
      after: "stockholders_equity",
      caption: "Total liabilities & equity",
      cy: "26410000",
      py: "23200000",
      change: "3210000",
      pct: "13.8",
      total: true,
    },
  ],
  final: [
    {
      after: "cost_of_goods_sold",
      caption: "Gross profit",
      cy: "19325520",
      py: "18410000",
      change: "915520",
      pct: "5.0",
    },
    {
      after: "interest_expense",
      caption: "Pre-tax income",
      cy: "2985520",
      py: "3040000",
      change: "-54480",
      pct: "-1.8",
    },
    {
      after: "other_assets",
      caption: "Total assets",
      cy: "26295520",
      py: "23200000",
      change: "3095520",
      pct: "13.3",
      total: true,
    },
    {
      after: "stockholders_equity",
      caption: "Total liabilities & equity",
      cy: "26295520",
      py: "23200000",
      change: "3095520",
      pct: "13.3",
      total: true,
    },
  ],
}; // fmt: skip
