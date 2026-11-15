// The Copperleaf CAS figure book as typed fixtures (C-01-T13; TASK-8031; C-01 §5.3; SPEC-655).
// Every figure is the handoff's (CLS-01, CLS-02, CLS-05, CLS-06, CLS-09, CLS-10, POR-11) at the E0
// clock, Mon 14 Sep 2026 9:24 AM CT; `fixtures/contracts/close-figures.test.ts` foots these against
// backend/tests/golden/scenario/brightwater_hale/copperleaf_close_figures.json, the same book the
// synthetic close slice is checked against. No kit sample data: no "13-task close run", no
// "Closed", no Elena Ruiz.
import type {
  CloseIssueOut,
  CloseIssuesOut,
  CloseListOut,
  ClosePersonOut,
  CloseProcedureOut,
  CloseReconciliationOut,
  CloseRowOut,
  CloseRunOut,
  CloseRunsOut,
  CloseStatementLineOut,
  CloseTaskGroupOut,
  FluxLineOut,
  FluxSetOut,
  PlanRowOut,
  PlanVersionOut,
  PortalQuestionsOut,
  ReconcilingItemOut,
  RequestTemplateOut,
  RunningClosesOut,
} from "@abacus/api-client";
import { CLOSE_IDS } from "./closes";
import { entityIdOf, slugOfClient } from "./clients";
import { slugOf } from "./people";
import { stableId } from "./prng";

export const COPPERLEAF = "Copperleaf Coffee Roasters, Inc.";
export const PERIOD = "2026-08";
const HASH = "0".repeat(64); // fixture versions carry a placeholder inputs hash

export const PEOPLE = {
  RM: "Raj Malhotra",
  PR: "Priya Raman",
  EG: "Ezra Gold",
  IV: "Ivy Vance",
  EW: "Erin Walsh",
  RF: "Rosa Fuentes",
  HV: "Helen Voss",
} as const;
type Initials = keyof typeof PEOPLE;

export function closePerson(initials: Initials): ClosePersonOut {
  const name = PEOPLE[initials];
  return { user_id: stableId(`user:${slugOf(name)}`), name, initials };
}

// --- CLS-01 the August portfolio --------------------------------------------------------------

type Row = [
  ref: string,
  client: string,
  status: CloseRowOut["status"],
  reconciled: number,
  total: number,
  issues: number,
  due: string,
  pastDue: number | null,
  pair: `${Initials}/${Initials}`,
  running?: boolean,
];

const ROWS: Row[] = [
  ["C1", COPPERLEAF, "in_progress", 9, 21, 7, "2026-09-08", 4, "RM/PR", true],
  ["C2", "Juniper & Oak Interiors, LLC", "delivered", 21, 21, 0, "2026-09-10", null, "EG/PR"],
  ["C3", "Two Rivers Brewing Co.", "in_progress", 13, 21, 3, "2026-09-15", null, "EG/HV"],
  ["C4", "Larkspur Floral, Inc.", "in_review", 21, 21, 2, "2026-09-15", null, "IV/HV"],
  ["C5", "Pinecrest Pediatrics, PC", "delivered", 21, 21, 0, "2026-09-09", null, "EW/PR"],
  ["C6", "Cedar Hollow Farms, LLC", "in_progress", 8, 21, 5, "2026-09-18", null, "EG/HV", true],
  ["C7", "Summit Line Logistics, Inc.", "in_progress", 12, 22, 4, "2026-09-15", null, "RF/HV"],
  ["C8", "Bramble & Finch Design, LLC", "in_review", 21, 21, 1, "2026-09-16", null, "IV/RF"],
  [
    "C9",
    "Hollis Creek Veterinary, PC",
    "in_progress",
    10,
    21,
    3,
    "2026-09-18",
    null,
    "EW/HV",
    true,
  ],
  ["C10", "Alder & Ash Furniture Co.", "in_progress", 15, 21, 2, "2026-09-16", null, "RF/PR"],
  ["C11", "Bluebird Bakery Co.", "in_progress", 6, 21, 6, "2026-09-10", 2, "IV/RF"],
  ["C12", "Canyon Pass Climbing Gym, LLC", "not_started", 0, 21, 0, "2026-09-20", null, "EG/HV"],
  ["C13", "Foxglove Studio, LLC", "in_review", 21, 21, 1, "2026-09-16", null, "IV/RF"],
  ["C14", "Granary Row Market, Inc.", "in_progress", 11, 21, 4, "2026-09-17", null, "RF/PR"],
  ["C15", "Ironwood Landscape Co.", "not_started", 0, 21, 0, "2026-09-21", null, "EW/HV"],
  ["C16", "Kettle & Kiln Pottery, LLC", "in_progress", 14, 21, 2, "2026-09-17", null, "IV/RF"],
  ["C17", "Lumen Dental Lab, Inc.", "in_review", 21, 21, 2, "2026-09-15", null, "EW/HV"],
  ["C18", "Maple & Main Hardware, Inc.", "in_progress", 10, 23, 5, "2026-09-18", null, "RF/PR"],
  ["C19", "Northfield Pet Clinic, PC", "in_progress", 12, 21, 3, "2026-09-17", null, "EG/HV"],
  ["C20", "Orchard Lane Wellness, LLC", "delivered", 21, 21, 0, "2026-09-11", null, "IV/RF"],
  [
    "C21",
    "Prairie Wind Solar Installers, Inc.",
    "not_started",
    0,
    21,
    0,
    "2026-09-25",
    null,
    "EW/HV",
  ],
  ["C22", "Quill & Press Printing Co.", "in_review", 21, 21, 1, "2026-09-16", null, "RF/PR"],
];

/** The CLS-01 row reference ("C1") for scenarios such as `hoverRow("C11")`. */
export const closeIdOfRef = (ref: string): string =>
  ref === "C1" ? CLOSE_IDS.august : stableId(`close:${ref.toLowerCase()}:${PERIOD}`);

function row([
  ref,
  client,
  status,
  rec,
  total,
  issues,
  due,
  pastDue,
  pair,
  running,
]: Row): CloseRowOut {
  const [prep, rev] = pair.split("/") as [Initials, Initials];
  const slug = slugOfClient(client);
  return {
    close_id: closeIdOfRef(ref),
    engagement_id: stableId(`engagement:${slug}:2026-close`),
    client_entity_id: entityIdOf(slug, client),
    client_name: client,
    period: PERIOD,
    status,
    on_hold: false,
    attest: false, // closes are non-attest (01 §9.7)
    accounts_reconciled: rec,
    accounts_total: total,
    reconciled_pct: Math.round((rec * 100) / total),
    open_issues: issues,
    due_on: due,
    days_past_due: pastDue,
    preparer: closePerson(prep),
    reviewer: closePerson(rev),
    running: running ?? false,
    run_no: ref === "C1" ? 2 : status === "not_started" ? 0 : 1,
    allowed_actions:
      status === "not_started" || status === "in_progress" ? ["close_run.start"] : [],
  };
}

export function closeRows(): CloseRowOut[] {
  return ROWS.map(row);
}

/** CLS-01 a: the list envelope with the four tiles and the summary line, through a filter. */
export function closesPortfolio(filter: (r: CloseRowOut) => boolean = () => true): CloseListOut {
  const all = closeRows();
  const items = all.filter(filter);
  const count = (s: CloseRowOut["status"][]) => items.filter((r) => s.includes(r.status)).length;
  return {
    items,
    tiles: {
      not_started: count(["not_started"]),
      in_progress: count(["in_progress"]),
      in_review: count(["in_review", "approved"]),
      delivered: count(["delivered", "locked"]),
    },
    summary: {
      open_issues: items.reduce((n, r) => n + r.open_issues, 0),
      past_due: items.filter((r) => r.days_past_due != null).length,
      running: items.filter((r) => r.running).length,
    },
    next_cursor: null,
  };
}

// --- CLS-02 runs ------------------------------------------------------------------------------

const RUN_1 = stableId("close-run:copperleaf:2026-08:1");
const RUN_2 = stableId("close-run:copperleaf:2026-08:2");
export const RUN_2_STARTED = "2026-09-14T09:06:00-05:00";
export const RUN_1_STARTED = "2026-09-02T08:15:00-05:00";

const A4410 = "Operating Checking (Front Range Bank) ••4410";
const AMEX = "Amex Business Card ••1009";

type Proc = [label: string, status: CloseProcedureOut["status"], meta: string, open?: number];
const GROUPS: [key: string, label: string, procs: Proc[]][] = [
  [
    "recategorize",
    "Recategorize Revenue and Expenses",
    [
      [A4410, "needs_attention", "1 agent-reported recategorization proposal · 1 open", 1],
      [AMEX, "done", "No issues"],
    ],
  ],
  [
    "reconcile_statements",
    "Reconcile to Statements",
    [
      [A4410, "needs_attention", "2 open · difference $0.00", 2],
      ["Payroll Checking (Front Range Bank) ••4428", "done", "No issues · Reconciled"],
      [AMEX, "running", "Running… cycle Jul 23–Aug 22 plus the card feed through Aug 31"],
    ],
  ],
  [
    "third_party_sales",
    "Reconcile Third Party Sales (Square, Shopify)",
    [
      ["Square", "done", "No issues · Reconciled · 21 transfers · net $71,482.36"],
      ["Shopify", "running", "Running…"],
    ],
  ],
  [
    "amortize_prepaids",
    "Identify and Amortize Prepaids",
    [["Prepaid insurance", "needs_attention", "1 open · Ties once posted", 1]],
  ],
  [
    "depreciate_fixed_assets",
    "Identify and Depreciate Fixed Assets",
    [
      [
        "Fixed asset register",
        "running",
        "Running… testing Sound Electric $3,200.00 against the $2,500 capitalization policy",
      ],
    ],
  ],
];

function groups(): CloseTaskGroupOut[] {
  return GROUPS.map(([key, label, procs]) => ({
    key,
    label,
    procedures: procs.map(([name, status, meta, open], i) => {
      const id = stableId(`close-procedure:${key}:${i}`);
      return {
        procedure_id: id,
        run_step_id: stableId(`run-step:${key}:${i}`),
        label: name,
        status,
        meta,
        open_count: open ?? 0,
      };
    }),
  }));
}

/** CLS-02 a: Run 2 at 9:24 AM, "6 of 9 complete", three at once. */
export function copperleafRun2(): CloseRunOut {
  const gs = groups();
  const procs = gs.flatMap((g) => g.procedures);
  return {
    run_id: RUN_2,
    run_no: 2,
    status: "running",
    started_by: closePerson("RM"),
    started_at: RUN_2_STARTED,
    finished_at: null,
    done: procs.filter((p) => p.status === "done" || p.status === "needs_attention").length,
    total: procs.length,
    running: procs.filter((p) => p.status === "running").length,
    open_issues: 7,
    read_only: false,
    groups: gs,
  };
}

/** The "Run 2 ⌄" history: Run 2 running and Run 1 22 of 22. */
export function copperleafRuns(): CloseRunsOut {
  return {
    items: [
      { run_id: RUN_2, run_no: 2, status: "running", total: 9, started_at: RUN_2_STARTED },
      {
        run_id: RUN_1,
        run_no: 1,
        status: "complete_with_exceptions",
        total: 22,
        started_at: RUN_1_STARTED,
      },
    ],
    ready_to_run: 0,
  };
}

/** The running pill: "Running closing agent · 3 closes"; Copperleaf's line is Run 2 · 6 of 9. */
export function runningCloses(): RunningClosesOut {
  return {
    items: closeRows()
      .filter((r) => r.running)
      .map((r) => ({
        close_id: r.close_id,
        client_name: r.client_name,
        period: r.period,
        run_id: r.close_id === CLOSE_IDS.august ? RUN_2 : stableId(`close-run:${r.close_id}`),
        run_no: r.close_id === CLOSE_IDS.august ? 2 : 1,
        done: r.close_id === CLOSE_IDS.august ? 6 : 0,
        total: r.close_id === CLOSE_IDS.august ? 9 : 0,
        started_at: RUN_2_STARTED,
      })),
  };
}

// --- CLS-05 Operating Checking ••4410 ---------------------------------------------------------

const STATEMENT = stableId("evidence-version:copperleaf:frontrange-4410-2026-08");
const region = (key: string, page: number, line: number) => ({
  page_no: page,
  bbox: [0.06, 0.18 + line * 0.045, 0.88, 0.04],
  citation_id: stableId(`citation:4410:${key}`),
});

type Stmt = [date: string, description: string, withdrawal: string | null, deposit: string | null];
const PAGE_2: Stmt[] = [
  ["2026-08-24", "SQUARE INC TRANSFER", null, "2427.05"],
  ["2026-08-25", "SQUARE INC TRANSFER", null, "7637.03"],
  ["2026-08-25", "ROCKY RIDGE DAIRY ACH PMT", "2860.00", null],
  ["2026-08-26", "SQUARE INC TRANSFER", null, "2058.31"],
  ["2026-08-27", "SQUARE INC TRANSFER", null, "2046.59"],
  ["2026-08-27", "ROCKY RIDGE DAIRY CO REFUND", null, "380.00"],
  ["2026-08-28", "SQUARE INC TRANSFER", null, "2131.10"],
  ["2026-08-31", "SQUARE INC TRANSFER", null, "2356.11"],
  ["2026-08-31", "TRANSFER TO ••4428 PAYROLL", "24600.00", null],
];

export const ISSUE_IDS = {
  soundElectric: stableId("issue:copperleaf:sound-electric"),
  accruedExpenses: stableId("issue:copperleaf:accrued-expenses"),
  check2281: stableId("issue:copperleaf:check-2281"),
  refund380: stableId("issue:copperleaf:refund-380"),
  prepaid: stableId("issue:copperleaf:prepaid"),
  payroll: stableId("issue:copperleaf:payroll-flux"),
  amexCycle: stableId("issue:copperleaf:amex-cycle"),
} as const;

/** CLS-05 a: difference $0.00 with two open items (the stale #2281 and the $380.00 refund). */
export function copperleafReconciliation4410(): CloseReconciliationOut {
  const statementLines: CloseStatementLineOut[] = PAGE_2.map(([date, description, w, d], i) => ({
    statement_line_id: stableId(`statement-line:4410:${i}`),
    txn_date: date,
    description,
    withdrawal: w,
    deposit: d,
    region: region(`line-${i}`, 2, i),
    matched: description !== "ROCKY RIDGE DAIRY CO REFUND",
    low_confidence: false,
  }));
  const item = (
    key: string,
    side: ReconcilingItemOut["side"],
    kind: ReconcilingItemOut["kind"],
    date: string,
    days: number,
    amount: string,
    extra: Partial<ReconcilingItemOut> = {},
  ): ReconcilingItemOut => ({
    item_id: stableId(`reconciling-item:4410:${key}`),
    side,
    kind,
    txn_date: date,
    days_at_period_end: days,
    amount,
    stale: false,
    ...extra,
  });
  return {
    reconciliation_id: stableId("reconciliation:copperleaf:4410:2026-08"),
    version: 2,
    account_external_id: "35",
    account_name: A4410,
    period_end: "2026-08-31",
    statement_evidence_version_id: STATEMENT,
    balance_per_bank: "184236.18",
    adjusted_bank: "184990.50",
    book_balance: "184610.50",
    adjusted_book: "184990.50",
    difference: "0.00",
    tally: "tie",
    items: [
      item("dit-square", "bank", "deposit_in_transit", "2026-08-31", 0, "6412.40"),
      item("check-2287", "bank", "outstanding_check", "2026-08-26", 5, "-3615.75", {
        ref: "#2287",
      }),
      item("check-2290", "bank", "outstanding_check", "2026-08-28", 3, "-802.33", {
        ref: "#2290",
      }),
      item("check-2281", "bank", "outstanding_check", "2026-02-19", 193, "-1240.00", {
        ref: "#2281",
        stale: true,
        issue_id: ISSUE_IDS.check2281,
      }),
      item("refund-380", "book", "unrecorded_deposit", "2026-08-27", 4, "380.00", {
        region: region("line-5", 2, 5),
        issue_id: ISSUE_IDS.refund380,
      }),
    ],
    statement_lines: statementLines,
    signed_off_by: null,
    sign_off_stale: false,
    sign_off_blockers: ["open_items"],
    engine_version: "reconciliation-1.0.0",
    inputs_hash: HASH,
  };
}

// --- CLS-06 the review queue ------------------------------------------------------------------

type Issue = [
  key: keyof typeof ISSUE_IDS,
  severity: CloseIssueOut["severity"],
  cls: CloseIssueOut["issue_class"],
  title: string,
  waiting?: boolean,
];
const ISSUES: Issue[] = [
  [
    "soundElectric",
    "medium",
    "flux",
    "Sound Electric $3,200.00 booked to Repairs & Maintenance — up 400% on July",
    true,
  ],
  [
    "accruedExpenses",
    "medium",
    "schedule",
    "Accrued expenses entry $14,900.00 is above the $10,000 other-accruals threshold",
  ],
  ["check2281", "low", "bank_rec", "Outstanding check #2281 dated Feb 2026 has not cleared"],
  [
    "refund380",
    "low",
    "bank_rec",
    "Vendor refund $380.00 on the Aug 27 statement is not recorded in the books",
  ],
  ["prepaid", "low", "schedule", "Prepaid insurance ties once the $700 August amortization posts"],
  ["payroll", "low", "flux", "Payroll up 12.5% on July — new hires, merit increases and overtime"],
  ["amexCycle", "low", "bank_rec", "Amex statement cycle ends Aug 22, not on the calendar month"],
];

/** CLS-06 a: Medium 2 + Low 5 = 7 = the Review badge; 4 notes never count. */
export function copperleafIssues(): CloseIssuesOut {
  const items: CloseIssueOut[] = ISSUES.map(([key, severity, cls, title, waiting]) => ({
    issue_id: ISSUE_IDS[key],
    title,
    severity,
    issue_class: cls,
    status: "open",
    waiting_on_client: waiting ?? false,
  }));
  return {
    open: items.length,
    by_severity: {
      medium: items.filter((i) => i.severity === "medium").length,
      low: items.filter((i) => i.severity === "low").length,
    },
    notes: 4,
    items,
    adjustments: { target: "CLS-07", label: "Adjustments" },
  };
}

// --- CLS-10 flux, August vs July --------------------------------------------------------------

type Flux = [key: string, caption: string, prior: number, current: number];
const FLUX: Flux[] = [
  ["revenue", "Revenue", 205_300, 214_600],
  ["cogs", "Cost of goods sold", 81_170, 84_860],
  ["payroll", "Payroll", 61_240, 68_910],
  ["rent", "Rent", 9_800, 9_800],
  ["merchant_fees", "Merchant fees", 4_710, 4_980],
  ["legal_professional", "Legal & professional fees", 4_800, 4_840],
  ["repairs_maintenance", "Repairs & maintenance", 640, 3_200],
  ["utilities_facilities", "Utilities & facilities", 2_960, 3_140],
  ["marketing", "Marketing", 3_980, 2_450],
  ["depreciation", "Depreciation", 2_140, 2_140],
  ["software", "Software & subscriptions", 1_180, 1_265],
  ["insurance", "Insurance", 700, 700],
  ["interest", "Interest expense", 525, 520],
];
const money = (n: number) => n.toFixed(2);

/** CLS-10 a: 13 lines tested, 2 over both thresholds (Payroll explained as a draft, Repairs not). */
export function copperleafFlux(): FluxSetOut {
  const lines: FluxLineOut[] = FLUX.map(([key, caption, prior, current]) => {
    const change = current - prior;
    const pct = Math.round((change * 1000) / prior) / 10;
    const over = Math.abs(pct) > 10 && Math.abs(change) > 2_500;
    const status: FluxLineOut["status"] = !over
      ? "within_threshold"
      : key === "payroll"
        ? "explained_draft"
        : "unexplained";
    return {
      line_id: stableId(`analytic-line:copperleaf:2026-08:${key}`),
      line_key: key,
      caption,
      prior: money(prior),
      current: money(current),
      change: money(change),
      change_pct: pct.toFixed(1),
      test: over ? "over_both" : "within",
      status,
      drivers:
        key === "payroll"
          ? (
              [
                ["New hires", 4_350],
                ["Merit increases", 1_850],
                ["Overtime", 1_470],
              ] as const
            ).map(([label, amount], i) => ({
              label,
              amount: money(amount),
              citation_id: stableId(`citation:payroll-register:${i}`),
            }))
          : [],
      row_version: 1,
    };
  });
  return {
    set_id: stableId("analytic-set:copperleaf:2026-08:mom"),
    basis: "mom",
    threshold_label: "10% and $2,500",
    tested: lines.length,
    explained: lines.filter((l) => l.status === "explained_draft" || l.status === "explained")
      .length,
    unexplained: lines.filter((l) => l.status === "unexplained").length,
    budget_available: false,
    lines,
    engine_version: "flux-1.0.0",
  };
}

// --- CLS-09 the close plan, v3 ----------------------------------------------------------------

type Plan = [
  cls: string,
  account: string,
  procedure: PlanRowOut["procedure"],
  method: string,
  evidence: string,
  source: PlanRowOut["source"],
  review: PlanRowOut["review_level"],
];
const S = "senior_signoff";
const M = "manager_approval";
const FA = "Beginning assets + additions − disposals";
const PLAN: Plan[] = [
  [
    "Bank",
    A4410,
    "reconciliation",
    "Bank statement → GL; outstanding items aged",
    "Bank statement",
    "bank_feed",
    S,
  ],
  [
    "Bank",
    "Payroll Checking (Front Range Bank) ••4428",
    "reconciliation",
    "Bank statement → GL",
    "Bank statement",
    "bank_feed",
    S,
  ],
  [
    "Bank",
    "Business Savings (Front Range Bank) ••4436",
    "reconciliation",
    "Bank statement → GL",
    "Bank statement",
    "client_upload",
    S,
  ],
  [
    "Accounts Receivable",
    "Accounts Receivable",
    "aging",
    "Subledger → GL; wholesale aging reviewed",
    "AR aging",
    "quickbooks_online",
    S,
  ],
  [
    "Other Current Assets",
    "Undeposited Funds",
    "clear_and_age",
    "Deposit detail → bank deposits",
    "Deposit detail",
    "quickbooks_online",
    S,
  ],
  [
    "Other Current Assets",
    "Square Clearing",
    "third_party_sales",
    "Gross − fees → net transfers → bank",
    "Square payout report",
    "client_upload",
    S,
  ],
  [
    "Other Current Assets",
    "Shopify Clearing",
    "third_party_sales",
    "Gross − fees − refunds → payouts → bank",
    "Shopify payout report",
    "client_upload",
    S,
  ],
  [
    "Other Current Assets",
    "Inventory",
    "rollforward",
    "Roast log (perpetual) → GL",
    "Inventory valuation report",
    "quickbooks_online",
    M,
  ],
  [
    "Other Current Assets",
    "Prepaid Insurance",
    "amortization",
    "Arrangement → monthly entry",
    "Policy declarations",
    "files",
    S,
  ],
  [
    "Fixed Assets",
    "Roasting Equipment",
    "rollforward",
    FA,
    "Asset register + invoices",
    "accrued_register",
    M,
  ],
  [
    "Fixed Assets",
    "Furniture & Fixtures",
    "rollforward",
    FA,
    "Asset register + invoices",
    "accrued_register",
    M,
  ],
  [
    "Fixed Assets",
    "Leasehold Improvements",
    "rollforward",
    FA,
    "Asset register + invoices",
    "accrued_register",
    M,
  ],
  [
    "Fixed Assets",
    "Accumulated Depreciation",
    "depreciation",
    "Calculate monthly, straight-line",
    "Asset register",
    "accrued_register",
    M,
  ],
  [
    "Credit Cards",
    AMEX,
    "reconciliation",
    "Statement → GL; cycle-date cutoff to month end",
    "Card statement + card feed",
    "client_upload",
    S,
  ],
  [
    "Accounts Payable",
    "Accounts Payable",
    "aging_cutoff",
    "Subledger → GL; unrecorded liabilities search",
    "AP aging",
    "client_upload",
    S,
  ],
  [
    "Other Current Liabilities",
    "Accrued Payroll",
    "accrual",
    "Days worked after the last pay period × rate; reverses next month",
    "Payroll register",
    "client_upload",
    S,
  ],
  [
    "Other Current Liabilities",
    "Accrued Expenses",
    "accrual",
    "Received-not-invoiced + recurring bills; reverses next month",
    "AP detail + receiving log",
    "quickbooks_online",
    M,
  ],
  [
    "Other Current Liabilities",
    "Deferred Revenue — Subscriptions",
    "rollforward",
    "Prior balance + billings − recognized → ending balance",
    "Subscription billing report",
    "client_upload",
    M,
  ],
  [
    "Other Current Liabilities",
    "Sales Tax Payable",
    "tie_to_return",
    "Collected vs remitted",
    "Sales tax liability report",
    "quickbooks_online",
    S,
  ],
  [
    "Other Current Liabilities",
    "Payroll Liabilities",
    "tie_to_filings",
    "Payroll register → GL; liabilities paid",
    "Payroll register",
    "client_upload",
    S,
  ],
  [
    "Long-Term Liabilities",
    "Equipment Loan (Front Range Bank)",
    "amortization",
    "Lender balance → GL; current portion split",
    "Loan statement",
    "client_upload",
    S,
  ],
  [
    "Income Statement",
    "Revenue & expenses",
    "recategorize",
    "Transaction coding review by account feed",
    "GL detail",
    "quickbooks_online",
    S,
  ],
  [
    "Income Statement",
    "Revenue & expenses",
    "flux",
    "Month over month vs threshold",
    "GL detail",
    "quickbooks_online",
    M,
  ],
];
export const REQUEST_TEMPLATES = [
  "Business Savings ••4436 statement",
  "Square payout report",
  "Shopify payout report",
  "Amex statement",
  "AP aging",
  "Payroll register",
  "Subscription billing report",
  "Loan statement",
] as const;

/** CLS-09 a: v3, published Jun 2, 2026 by Priya Raman; 23 = Manager 8 + Senior 15; 8 requests. */
export function copperleafPlanV3(): PlanVersionOut {
  const rows: PlanRowOut[] = PLAN.map(
    ([cls, account, procedure, method, evidence, source, review], i) => ({
      row_id: stableId(`close-plan-row:copperleaf:v3:${i}`),
      position: i,
      account_name: account,
      account_class: cls,
      procedure,
      method,
      evidence_required: evidence,
      source,
      review_level: review,
      frequency: "monthly",
      drafted: false,
      adopted: true,
      changed_from_previous: false,
    }),
  );
  const requests: RequestTemplateOut[] = REQUEST_TEMPLATES.map((title, i) => ({
    template_id: stableId(`close-request-template:copperleaf:v3:${i}`),
    title,
    category_path: [],
    due_business_day: 3,
    client_visible: true,
  }));
  return {
    plan_id: stableId("close-plan:copperleaf"),
    version: 3,
    status: "published",
    effective_from: "2026-06",
    drafted_by: "Priya Raman",
    published_by: closePerson("PR"),
    published_at: "2026-06-02T10:00:00-05:00",
    publish_requested: false,
    rows,
    request_templates: requests,
    tally: {
      procedures: rows.length,
      manager: rows.filter((r) => r.review_level === M).length,
      senior: rows.filter((r) => r.review_level === S).length,
      requests_per_month: requests.length,
    },
    allowed_actions: ["close_plan.edit"],
    row_version: 1,
  };
}

// --- POR-11 the client's questions ------------------------------------------------------------

/** POR-11 a: three questions to answer, in the client's words only (QC-9). */
export function copperleafPortalQuestions(): PortalQuestionsOut {
  const asked = "2026-09-11T10:00:00-05:00";
  const q = (key: string, client_wording: string, context_line: string) => ({
    question_id: stableId(`transaction-question:copperleaf:${key}`),
    client_wording,
    context_line,
    status: "open" as const,
    asked_by_name: "Raj Malhotra",
    asked_at: asked,
    answered_at: null,
  });
  return {
    items: [
      q(
        "check-2281",
        "Check #2281 for $1,240.00 to Highline Espresso Service, dated February 19, 2026, still hasn't cleared. Was it lost, voided or reissued?",
        "Front Range Bank ••4410 · asked by Raj Malhotra Sep 11",
      ),
      q(
        "refund-380",
        "Front Range Bank shows a $380.00 deposit from Rocky Ridge Dairy Co. on August 27. What was it for?",
        "Front Range Bank ••4410 · August statement",
      ),
      q(
        "sound-electric",
        "What was the $3,200 payment to Sound Electric?",
        "Front Range Bank ••4410 · check #2285 · asked by Raj Malhotra Sep 11",
      ),
    ],
  };
}
