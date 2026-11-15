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
