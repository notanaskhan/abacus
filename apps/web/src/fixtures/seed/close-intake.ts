// CLS-03's figure book (C-01-T35): Copperleaf August's intake tree (8 recurring requests from close
// plan v3 + 1 ad hoc; 7 received, 2 requested), Ben Ashby's Square payout report as the viewer
// shows it (21 transfers, 5,143 transactions, gross 73,166.90, fees 1,684.54, net 71,482.36), the
// summary card's code totals with their `sheet_cell` citations, and the August questionnaire (4
// of 5 answered). Every figure and word is the handoff's (CLS-03 A–H, the R2 revision).
import type {
  CloseQuestionnaireOut,
  IntakeSummaryOut,
  RequestNodeOut,
  RequestTreeOut,
  ViewerTextOut,
} from "@abacus/api-client";
import { CLOSE_IDS } from "./closes";
import { stableId } from "./prng";

export const SQUARE_VERSION = stableId("evidence-version:copperleaf:square-2026-08");
export const AMEX_VERSION = stableId("evidence-version:copperleaf:amex-2026-08");
export const SQUARE_FILE = "square-2026-08-01_2026-08-31-payouts.xlsx";

type Req = [
  key: string,
  title: string,
  sub: string,
  status: NonNullable<RequestNodeOut["status"]>,
  due?: string,
];

function req(
  [key, title, , status, due]: Req,
  extra: Partial<RequestNodeOut> = {},
): RequestNodeOut {
  const received = status !== "requested";
  const node: RequestNodeOut = {
    node_id: `r:${key}`,
    kind: "request",
    title,
    request_item_id: stableId(`request-item:copperleaf:2026-08:${key}`),
    status,
    received: received ? 1 : 0,
    total: 1,
    client_visible: true,
    linked: received ? 1 : 0,
    screening: received ? "clear" : null,
    overdue: false,
    rerun_plan_row_ids: [],
    evidence_version_id: key === "square" ? SQUARE_VERSION : key === "amex" ? AMEX_VERSION : null,
    due_on: due ?? null,
    children: [],
  };
  return { ...node, ...extra };
}

/** The sub-line each row shows (handoff A's tree). */
export const SUBLINES: Readonly<Record<string, string>> = {
  square: "Matched to uploaded document",
  shopify: "Incorporated Sep 3",
  savings: "Requested Sep 1",
  amex: "Incorporated Aug 25",
  subscriptions: "Incorporated Sep 3",
  payroll: "Incorporated Sep 2",
  loan: "Incorporated Sep 2",
  ap: "Incorporated Sep 2",
  sound: "Requested Sep 11",
};

const ROWS: Record<string, Req> = {
  square: ["square", "Square payouts — August", "", "pending_incorporation", "2026-09-03"],
  shopify: ["shopify", "Shopify payouts — August", "", "incorporated"],
  savings: ["savings", "Front Range Bank statement — August (Savings ••4436)", "", "requested"],
  amex: ["amex", "Amex ••1009 statement — cycle ending Aug 22", "", "incorporated"],
  subscriptions: ["subscriptions", "Subscription billing report — August", "", "incorporated"],
  payroll: ["payroll", "Payroll register — August (pay dates Aug 3, 17, 31)", "", "incorporated"],
  loan: ["loan", "Equipment loan statement — August", "", "incorporated"],
  ap: ["ap", "AP aging — Aug 31", "", "incorporated"],
  sound: ["sound", "Sound Electric invoice — Aug 18 ($3,200)", "", "requested"],
};

function category(id: string, title: string, children: RequestNodeOut[]): RequestNodeOut {
  return {
    node_id: `c:${id}`,
    kind: "category",
    title,
    received: children.reduce((n, c) => n + (c.received ?? 0), 0),
    total: children.reduce((n, c) => n + (c.total ?? 0), 0),
    client_visible: true,
    linked: 0,
    overdue: false,
    rerun_plan_row_ids: [],
    children,
  };
}

export const SQUARE_PLAN_ROW = stableId("close-plan-row:copperleaf:v3:square");

/** CLS-03 a: the tree at 9:02 AM; `incorporated` (b) moves Square on and offers its re-run. */
export function copperleafRequestTree(state: "a" | "b" | "g" = "a"): RequestTreeOut {
  const square =
    state === "b"
      ? req(ROWS.square as Req, { status: "incorporated", rerun_plan_row_ids: [SQUARE_PLAN_ROW] })
      : req(ROWS.square as Req);
  const amex = req(ROWS.amex as Req, { screening: "flagged" });
  return {
    close_id: CLOSE_IDS.august,
    published: true,
    publishes_on: "2026-09-01",
    plan_version: 3,
    marked_done_by: null,
    nodes: [
      category("bank", "Bank & Cash Accounts", [
        category("bank/statements", "Bank statements and merchant payouts", [
          square,
          req(ROWS.shopify as Req),
          req(ROWS.savings as Req),
        ]),
        category("bank/cards", "Credit card statements", [
          state === "g" ? amex : req(ROWS.amex as Req),
        ]),
      ]),
      category("revenue", "Revenue", [req(ROWS.subscriptions as Req)]),
      category("payroll", "Payroll", [req(ROWS.payroll as Req)]),
      category("loans", "Loans & Payables", [req(ROWS.loan as Req), req(ROWS.ap as Req)]),
      category("questions", "Questions from review", [req(ROWS.sound as Req)]),
      category("misc", "Miscellaneous", []),
    ],
  };
}

/** CLS-03 f: September before BD1, nothing published yet. */
export function septemberRequestTree(): RequestTreeOut {
  return {
    close_id: CLOSE_IDS.september,
    published: false,
    publishes_on: "2026-10-01",
    plan_version: 3,
    marked_done_by: null,
    nodes: [],
  };
}

// The payout report as the viewer prints it: Transfer date · Sales period · Transactions · Gross ·
// Fees · Net, then the total row.
const SQUARE_ROWS: readonly (readonly string[])[] = [
  ["2026-08-03", "07-31 → 08-02", "545", "7,746.40", "178.32", "7,568.08"],
  ["2026-08-04", "08-03", "146", "2,074.24", "47.76", "2,026.48"],
  ["2026-08-05", "08-04", "160", "2,284.48", "52.60", "2,231.88"],
  ["2026-08-06", "08-05", "155", "2,207.28", "50.82", "2,156.46"],
  ["2026-08-07", "08-06", "145", "2,067.70", "47.61", "2,020.09"],
  ["2026-08-10", "08-07 → 08-09", "538", "7,642.20", "175.95", "7,466.25"],
  ["2026-08-11", "08-10", "145", "2,073.07", "47.73", "2,025.34"],
  ["2026-08-12", "08-11", "146", "2,082.54", "47.95", "2,034.59"],
  ["2026-08-13", "08-12", "157", "2,233.96", "51.43", "2,182.53"],
  ["2026-08-14", "08-13", "170", "2,416.48", "55.64", "2,360.84"],
  ["2026-08-17", "08-14 → 08-16", "541", "7,683.38", "176.90", "7,506.48"],
  ["2026-08-18", "08-17", "174", "2,471.30", "56.90", "2,414.40"],
  ["2026-08-19", "08-18", "162", "2,303.18", "53.03", "2,250.15"],
  ["2026-08-20", "08-19", "156", "2,221.34", "51.14", "2,170.20"],
  ["2026-08-21", "08-20", "174", "2,484.25", "57.20", "2,427.05"],
  ["2026-08-24", "08-21 → 08-23", "550", "7,817.00", "179.97", "7,637.03"],
  ["2026-08-25", "08-24", "148", "2,106.82", "48.51", "2,058.31"],
  ["2026-08-26", "08-25", "147", "2,094.82", "48.23", "2,046.59"],
  ["2026-08-27", "08-26", "153", "2,181.32", "50.22", "2,131.10"],
  ["2026-08-28", "08-27", "169", "2,411.63", "55.52", "2,356.11"],
  ["2026-08-31", "08-28 → 08-30", "462", "6,563.51", "151.11", "6,412.40"],
  ["Total", "", "5,143", "73,166.90", "1,684.54", "71,482.36"],
];
export const SQUARE_HEADER = [
  "Transfer date",
  "Sales period",
  "Transactions",
  "Gross",
  "Fees",
  "Net",
];

export function squarePayoutText(): ViewerTextOut {
  return {
    items: [],
    truncated: false,
    sheets: [{ name: "Payouts", rows: [SQUARE_HEADER, ...SQUARE_ROWS.map((r) => [...r])] }],
  };
}

/** The total row's cells, as the summary's `sheet_cell` citations name them (row 23). */
export const CITED_CELLS = {
  transactions: "C23",
  gross: "D23",
  fees: "E23",
  net: "F23",
} as const;

export function squareSummary(agentOn = true): IntakeSummaryOut {
  return {
    evidence_version_id: SQUARE_VERSION,
    label: agentOn ? "summarized_by_agent" : "totals_from_file",
    figures: [
      {
        key: "transactions",
        label: "Transactions",
        count: 5143,
        citation_id: stableId("cite:square:C23"),
      },
      {
        key: "gross",
        label: "Gross sales",
        amount: "73166.90",
        citation_id: stableId("cite:square:D23"),
      },
      {
        key: "fees",
        label: "Processing fees",
        amount: "1684.54",
        citation_id: stableId("cite:square:E23"),
      },
      {
        key: "net",
        label: "Net to bank",
        amount: "71482.36",
        citation_id: stableId("cite:square:F23"),
      },
    ],
    paragraph: agentOn
      ? "The spreadsheet lists 21 Square transfers to Front Range Bank ••4410 dated Aug 3 to Aug 31, 2026, covering card sales from Jul 31 to Aug 30. For each transfer it shows the sales period, transaction count, gross sales, processing fees and the net amount sent to the bank: 5,143 transactions, gross $73,166.90 and fees $1,684.54, with total net $71,482.36."
      : null,
    run_id: null,
  };
}

export function augustQuestionnaire(): CloseQuestionnaireOut {
  const ben = "Ben Ashby · Sep 2";
  return {
    answered: 4,
    total: 5,
    items: [
      {
        question: "Did Copperleaf open or close any bank, card or loan accounts in August?",
        answer: "No",
        answered_by: ben,
      },
      {
        question: "Did you buy equipment or make improvements over $2,500?",
        answer: null,
        answered_by: null,
      },
      {
        question: "Any owner distributions outside payroll?",
        answer: "Yes — $12,000 to Tess Moreno on Aug 31",
        answered_by: ben,
      },
      {
        question: "Any customer refunds or disputes open at month end?",
        answer: "No",
        answered_by: ben,
      },
      {
        question: "New vendors paid $2,000 or more without a W-9?",
        answer: "Mile High Window Cleaning (W-9 requested)",
        answered_by: ben,
      },
    ],
  };
}
