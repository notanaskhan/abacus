// The names and figures the gallery's specimens show (F-05-T33; F-05 "Fixture scenarios"; plan 04
// lint L10). They are the Brightwater Hale seed's own, at E0 (Mon Sep 14, 2026, 9:24 AM CT): the
// app's seed test (apps/web/src/fixtures/specimen-figures.test.ts) checks every one against the seed
// and that each sum foots. Kit sample data is never ported (DF-35).

import { FELD_T3_FOOTINGS } from "./feld-t3";

/** E0: the demo instant every specimen is drawn at. */
export const E0 = "2026-09-14T09:24:00-05:00";

export const FIRM = "Brightwater Hale";
export const FELD = "Jonah & Claire Feld";
export const RIDGELINE = "Ridgeline Property Partners, LP";
export const COPPERLEAF = "Copperleaf Coffee Roasters, Inc.";
export const NORTHWIND = "Northwind Robotics, Inc.";
export const NORTHWIND_PLAN = "Northwind Robotics 401(k) Plan";
export const GRANITE_PEAK = "Granite Peak Outdoor Supply, Inc.";

/** Staff the specimens name; each is a seat holder in the seed. */
export const STAFF = {
  hannah: "Hannah Leclerc",
  samuel: "Samuel Ito",
  kevin: "Kevin Osei",
  priya: "Priya Raman",
  margaret: "Margaret Okonkwo",
  raj: "Raj Malhotra",
  daniel: "Daniel Reyes",
  olivia: "Olivia Brandt",
} as const;

/** Persona slugs the specimens are seen as (`?as=`), including F-05-T33's two. */
export const PERSONAS = ["hannah-leclerc", "samuel-ito", "jonah-feld", "dana-whitley"] as const;

/**
 * Northwind PY2025 (blueprint 01 §9.4), as decimal strings. Unadjusted plus the contributions
 * receivable foots to the net assets available at Dec 31, 2025.
 */
export const NORTHWIND_FIGURES = {
  netAssetsUnadjusted: "16812400.00",
  contributionsReceivable: "48600.00",
  netAssetsAvailable20251231: "16861000.00",
  netAssetsAvailable20250101: "14228500.00",
  /** The Harborline Trust Company summary of net trust assets the trial balance ties to (TPL-02). */
  investmentsAtFairValue: "16500000.00",
  participantNotes: "312400.00",
} as const;

/**
 * Northwind's change in net assets over PY2025, as a server would send it with a variance cell:
 * the change foots Jan 1 to Dec 31 (FOOTINGS); the ratio is the change over the Jan 1 base.
 */
export const NORTHWIND_CHANGE = {
  netAssetsChange: "2632500.00",
  ratio: "0.1850",
} as const;

/** Request lists a specimen counts (blueprint 01 §9.3): the seed's own items. */
export const REQUEST_COUNTS = {
  northwind: { received: 11, total: 24 },
  feld: { received: 5, total: 7 },
  granitePeak: { sent: 0, total: 41 },
} as const;

/** TY2025 returns by office (TPL-12): Chicago, Denver, New York. */
export const RETURNS_BY_OFFICE = { Chicago: 98, Denver: 64, "New York": 62 } as const;

/**
 * Northwind's trial balance workbook (trust basis; documents.py `_TB_LINES`, blueprint §9.4):
 * account, name, debit, credit, as the grid specimen draws it. Debits and credits foot to the
 * same 17,663,450.00 (FOOTINGS).
 */
export const NORTHWIND_TB: readonly (readonly [string, string, string, string])[] = [
  ["1110", "KRS 500 Index Fund", "6120450.00", ""],
  ["1120", "KRS Target 2035 Fund", "2384910.00", ""],
  ["1130", "KRS Target 2045 Fund", "2915330.00", ""],
  ["1140", "KRS Bond Index Fund", "1408220.00", ""],
  ["1150", "KRS International Index Fund", "902610.00", ""],
  ["1160", "Harborline Stable Value Fund", "1163480.00", ""],
  ["1200", "Self-directed brokerage (BrokerWindow)", "1605000.00", ""],
  ["1300", "Notes receivable from participants", "312400.00", ""],
  ["3000", "Net assets available for benefits, January 1, 2025", "", "14228500.00"],
  ["4100", "Contributions received", "", "1318300.00"],
  ["4200", "Net appreciation in fair value of investments", "", "1755990.00"],
  ["4300", "Interest and dividends", "", "342860.00"],
  ["4400", "Interest income on notes receivable from participants", "", "17800.00"],
  ["5100", "Benefits paid to participants", "812650.00", ""],
  ["5200", "Administrative expenses", "38400.00", ""],
];

/**
 * Ridgeline Property Partners, LP's TY2025 K-1s (blueprint 01 §9.4): box 2 net rental real estate
 * income, box 5 interest, box 18A tax-exempt interest and box 19A distributions per partner, all
 * Draft (pre-release) on Sep 14. The five foot to Schedule K (FOOTINGS); Jonah Feld's is the K-1
 * TPL-03 reviews.
 */
export const RIDGELINE_K1S: readonly {
  partner: string;
  box2: string;
  box5: string;
  box18a: string;
  box19a: string;
}[] = [
  { partner: "Ridgeline GP LLC", box2: "24632", box5: "368", box18a: "124", box19a: "12000" },
  { partner: "Meera Shah", box2: "468008", box5: "6992", box18a: "2356", box19a: "228000" },
  {
    partner: "Pell Street Ventures LLC",
    box2: "400270",
    box5: "5980",
    box18a: "2015",
    box19a: "180000",
  },
  { partner: "Pell Street II LLC", box2: "30790", box5: "460", box18a: "155", box19a: "30000" },
  { partner: "Jonah Feld", box2: "307900", box5: "4600", box18a: "1550", box19a: "150000" },
];

/** Schedule K: the five K-1s' totals (blueprint 01 §9.4). */
export const RIDGELINE_SCHEDULE_K = {
  box2: "1231600",
  box5: "18400",
  box18a: "6200",
  box19a: "600000",
} as const;

/**
 * Jonah Feld's draft Ridgeline K-1 (TPL-03): Part III boxes and the Item L capital account as
 * drafted (blueprint 01 §9.4; 25% beginning and ending). Item L foots: 1,500,000 + 250,000 +
 * 312,500 − 150,000 = 1,912,500.
 */
export const FELD_K1 = {
  box2: "307900",
  box5: "4600",
  box18a: "1550",
  box19a: "150000",
  beginningCapital: "1500000",
  capitalContributed: "250000",
  currentYearIncome: "312500",
  withdrawals: "-150000",
  endingCapital: "1912500",
} as const;

/**
 * Halvard Securities' 2025 consolidated 1099 for the Felds (blueprint 01 §9.4) and the Form 1040
 * lines TPL-03b draws from it: 3b = 1099-DIV 1a, 3a = 1b, 2b = 1099-INT 1 + Ridgeline box 5.
 */
export const FELD_HALVARD = {
  ordinaryDividends: "14820",
  qualifiedDividends: "11960",
  interest: "2310",
} as const;

export const FELD_1040_LINES = {
  line2a: "1550",
  line2b: "6910",
  line3a: "11960",
  line3b: "14820",
} as const;

/**
 * Copperleaf's Operating Checking (Front Range Bank) ••4410 reconciliation at Aug 31, 2026 (blueprint
 * 01 §9, CLS-05; TPL-09b): bank 184,236.18 + deposit in transit 6,412.40 − outstanding checks
 * 5,658.08 = adjusted bank 184,990.50; book 184,610.50 + unrecorded vendor refund 380.00 = adjusted
 * book 184,990.50; difference 0.00. It shows `tie`, not Reconciled, while #2281 and the refund are
 * open.
 */
export const COPPERLEAF_BANK_REC = {
  bank: "184236.18",
  depositInTransit: "6412.40",
  outstandingChecks: [
    { id: "2281", label: "#2281 · Feb 19, 2026 · stale", amount: "-1240.00", stale: true },
    { id: "2287", label: "#2287 · Aug 26, 2026", amount: "-3615.75", stale: false },
    { id: "2290", label: "#2290 · Aug 28, 2026", amount: "-802.33", stale: false },
  ],
  totalOutstanding: "-5658.08",
  adjustedBank: "184990.50",
  book: "184610.50",
  unrecordedRefund: "380.00",
  adjustedBook: "184990.50",
  difference: "0.00",
} as const;

/** Every footing a specimen draws: `parts` add up to `total` (checked in the seed test). */
export const FOOTINGS: readonly { name: string; parts: readonly string[]; total: string }[] = [
  {
    name: "Northwind net assets at Dec 31, 2025",
    parts: [NORTHWIND_FIGURES.netAssetsUnadjusted, NORTHWIND_FIGURES.contributionsReceivable],
    total: NORTHWIND_FIGURES.netAssetsAvailable20251231,
  },
  {
    name: "Northwind net assets over PY2025",
    parts: [NORTHWIND_FIGURES.netAssetsAvailable20250101, NORTHWIND_CHANGE.netAssetsChange],
    total: NORTHWIND_FIGURES.netAssetsAvailable20251231,
  },
  {
    name: "Northwind trial balance tie to the net trust assets at Dec 31, 2025 (TPL-02)",
    parts: [NORTHWIND_FIGURES.investmentsAtFairValue, NORTHWIND_FIGURES.participantNotes],
    total: NORTHWIND_FIGURES.netAssetsUnadjusted,
  },
  {
    name: "Northwind trial balance debits",
    parts: NORTHWIND_TB.map((l) => l[2]).filter((v) => v !== ""),
    total: "17663450.00",
  },
  {
    name: "Northwind trial balance credits",
    parts: NORTHWIND_TB.map((l) => l[3]).filter((v) => v !== ""),
    total: "17663450.00",
  },
  ...FELD_T3_FOOTINGS,
  {
    name: "Feld K-1 Item L ending capital (TPL-03)",
    parts: [
      FELD_K1.beginningCapital,
      FELD_K1.capitalContributed,
      FELD_K1.currentYearIncome,
      FELD_K1.withdrawals,
    ],
    total: FELD_K1.endingCapital,
  },
  {
    name: "Feld Form 1040 line 2b taxable interest (TPL-03b)",
    parts: [FELD_HALVARD.interest, FELD_K1.box5],
    total: FELD_1040_LINES.line2b,
  },
  ...(["box2", "box5", "box18a", "box19a"] as const).map((box) => ({
    name: `Ridgeline Schedule K ${box} (five K-1s)`,
    parts: RIDGELINE_K1S.map((k) => k[box]),
    total: RIDGELINE_SCHEDULE_K[box],
  })),
  {
    name: "Copperleaf ••4410 outstanding checks (TPL-09b)",
    parts: COPPERLEAF_BANK_REC.outstandingChecks.map((c) => c.amount),
    total: COPPERLEAF_BANK_REC.totalOutstanding,
  },
  {
    name: "Copperleaf ••4410 adjusted bank balance (TPL-09b)",
    parts: [
      COPPERLEAF_BANK_REC.bank,
      COPPERLEAF_BANK_REC.depositInTransit,
      COPPERLEAF_BANK_REC.totalOutstanding,
    ],
    total: COPPERLEAF_BANK_REC.adjustedBank,
  },
  {
    name: "Copperleaf ••4410 adjusted book balance (TPL-09b)",
    parts: [COPPERLEAF_BANK_REC.book, COPPERLEAF_BANK_REC.unrecordedRefund],
    total: COPPERLEAF_BANK_REC.adjustedBook,
  },
  {
    name: "Copperleaf ••4410 difference (TPL-09b)",
    parts: [COPPERLEAF_BANK_REC.adjustedBank, `-${COPPERLEAF_BANK_REC.adjustedBook}`],
    total: COPPERLEAF_BANK_REC.difference,
  },
  {
    name: "TY2025 returns by office",
    parts: Object.values(RETURNS_BY_OFFICE).map(String),
    total: "224",
  },
];

/**
 * Northwind's PBC list as the TPL-02 canvas draws it (blueprint 01 §9.3; AUD-03 "Totals: 24
 * requests; 11 received; 1 needs review; 12 requested"): the seed's categories, titles and
 * statuses in the seed's order, which is already Missing first inside each category. The paths
 * are the received files' names, verbatim from the TPL-02 handoff.
 */
export const NORTHWIND_PBC: readonly {
  category: string;
  title: string;
  status: "received" | "review" | "requested";
  path?: string;
}[] = [
  {
    category: "Plan documents",
    title: "Trust agreement — Harborline Trust Company",
    status: "requested",
  },
  {
    category: "Plan documents",
    title: "IRS opinion letter on the pre-approved plan document",
    status: "requested",
  },
  {
    category: "Plan documents",
    title: "Plan document & amendments",
    status: "received",
    path: "initial-input/Northwind 401k Plan Document 2021 restatement.pdf",
  },
  {
    category: "Plan documents",
    title: "Adoption agreement",
    status: "received",
    path: "initial-input/Northwind Adoption Agreement 2024 amendment.pdf",
  },
  {
    category: "Plan documents",
    title: "Summary plan description",
    status: "received",
    path: "initial-input/Northwind SPD 2025.pdf",
  },
  {
    category: "Trust / Recordkeeper Reports",
    title: "Certified trust report (full year, signed)",
    status: "review",
  },
  {
    category: "Trust / Recordkeeper Reports",
    title: "Withdrawals / distributions report",
    status: "requested",
  },
  {
    category: "Trust / Recordkeeper Reports",
    title: "Summary of net trust assets",
    status: "received",
    path: "initial-input/Harborline Net Trust Assets 12-31-2025.pdf",
  },
  {
    category: "Trust / Recordkeeper Reports",
    title: "Schedule of Account Balances",
    status: "received",
    path: "initial-input/Keystone Account Balances PY2025.xlsx",
  },
  {
    category: "Trust / Recordkeeper Reports",
    title: "Annual loan balance roll-forward",
    status: "received",
    path: "initial-input/Keystone Loan Rollforward 2025.xlsx",
  },
  {
    category: "Trust / Recordkeeper Reports",
    title: "Brokerage / SDBA asset detail — BrokerWindow",
    status: "received",
    path: "initial-input/BrokerWindow Asset Detail 2025.pdf",
  },
  { category: "Census & Payroll", title: "W-3 Form", status: "requested" },
  { category: "Census & Payroll", title: "Opt-Out Elections", status: "requested" },
  { category: "Census & Payroll", title: "Pay Rate Authorizations", status: "requested" },
  { category: "Census & Payroll", title: "YTD payroll register", status: "requested" },
  {
    category: "Census & Payroll",
    title: "Employee Census File",
    status: "received",
    path: "initial-input/Northwind Census PY2025.xlsx",
  },
  {
    category: "Census & Payroll",
    title: "Contribution Reports — PayGrid",
    status: "received",
    path: "initial-input/PayGrid Contribution Detail 2025.xlsx",
  },
  {
    category: "Census & Payroll",
    title: "Quarterly 941 Forms",
    status: "received",
    path: "initial-input/941 Filings 2025 Q1-Q4.pdf",
  },
  {
    category: "Form 5500 & SOC 1",
    title: "Bridge letter — Keystone, Oct–Dec 2025",
    status: "requested",
  },
  {
    category: "Form 5500 & SOC 1",
    title: "Draft Form 5500 & Schedule H — Summit Plan Administrators",
    status: "requested",
  },
  { category: "Form 5500 & SOC 1", title: "ERISA 408(b)(2) fee disclosure", status: "requested" },
  {
    category: "Form 5500 & SOC 1",
    title: "SOC 1 Type 2 — Keystone Retirement Services",
    status: "received",
    path: "initial-input/Keystone SOC1 Type2 Oct24-Sep25.pdf",
  },
  {
    category: "Cash",
    title: "Schedule of cash accounts, confirmations, and statements",
    status: "requested",
  },
  {
    category: "Compliance & other",
    title: "Participant Complaints Log and Support",
    status: "requested",
  },
];
