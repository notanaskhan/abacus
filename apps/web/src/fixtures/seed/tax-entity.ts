// T-05-T13 (TASK-6812; SPEC-651; T-05 §5.3): Ridgeline Property Partners, LP's 2025 Form 1065 in
// fixture mode, for the T-05 screens' 57 artboards (TXP-00, 01, 02, 05, 06, 07, 10, 11). Shapes are
// the generated client's workbook v1 types (`tax/workbook_contract.py`, T-05-T06). Figures are
// whole-dollar decimal strings, verbatim from the handoff (TXP-02's trial balance, TXP-06's
// structure, TXP-00's runs); totals are the server's, never summed in the browser (ADR-050).
// Synthetic only.
import type {
  AgentRunOut,
  RunItemOut,
  RunItemsOut,
  WorkbookPartnersOut,
  WorkbookRunRowOut,
  WorkbookTalliesOut,
  WorkbookTbRowOut,
  WorkbookTbTotalOut,
  WorkbookTrialBalanceOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

/** One step of a scripted run (the shape `domain/agents`' ScriptedRunSource reads). */
export interface ScriptStep {
  page: RunItemsOut;
  afterMs: number;
}

export const RIDGELINE_RETURN_ID = stableId("tax-return:ridgeline-2025-1065");
export const PERSONAS = { olivia: "olivia-brandt", samuel: "samuel-ito" } as const;

/** The artboards' clocks (the screen contracts' "Demo clock" column). */
export const CLOCKS = {
  e0: "2026-09-14T09:24:00-05:00",
  approvedL2: "2026-09-14T09:40:00-05:00",
  fixApproved: "2026-09-14T09:51:00-05:00",
  afterFix: "2026-09-14T09:52:00-05:00",
  run1: "2026-09-08T10:02:00-05:00",
  idle: "2026-06-02T09:00:00-05:00",
} as const;

/** Which workbook snapshot an artboard reads. */
export type Snapshot = "run1" | "run2" | "run3" | "afterFix" | "idle" | "harborview";

type Row = readonly [string, string, string | null, string, string, string, string];
// account, name, form line, UTB, AJE, RJE, TJE (TXP-02; the tax basis is UTB + AJE + RJE + TJE).
const TB: readonly Row[] = [
  ["1000", "Cash — operating", "L1", "693667", "0", "0", "0"],
  ["1100", "Tenant receivables", "L2a", "96000", "0", "0", "0"],
  ["1200", "Municipal bond fund", "L5", "240000", "0", "0", "0"],
  ["1300", "Escrows & other assets", "L13", "158000", "0", "0", "0"],
  ["1500", "Land", "L11", "3600000", "0", "0", "0"],
  ["1600", "Buildings & improvements", "L9a", "15752000", "0", "0", "0"],
  ["1650", "Accumulated depreciation", "L9b", "-2625167", "0", "0", "0"],
  ["2000", "Accounts payable", "L15", "-120000", "0", "0", "0"],
  ["2050", "Accrued expenses", "L17", "-75500", "-18500", "0", "0"],
  ["2100", "Tenant security deposits", "L17", "-121800", "0", "0", "0"],
  ["2500", "Mortgage notes payable (nonrecourse)", "L18", "-10712500", "0", "0", "0"],
  ["3000", "Partners' capital — beginning", "L21", "-5960000", "0", "0", "0"],
  ["3100", "Partner contributions", "M-2 2a", "-250000", "0", "0", "0"],
  ["3200", "Partner distributions", "M-2 6a", "600000", "0", "0", "0"],
  ["4000", "Rental income", "8825 Rents", "-3776500", "0", "0", "0"],
  ["4100", "Parking & other property income", "8825 Rents", "-96400", "0", "0", "0"],
  ["4500", "Interest income", "K 5", "-18400", "0", "0", "0"],
  ["4510", "Tax-exempt interest (book)", "M-3 perm.", "-6200", "0", "0", "6200"],
  ["4510-T", "Tax-exempt interest — Sch K 18a (tax only)", "K 18a", "0", "0", "0", "-6200"],
  ["5000", "Repairs & maintenance", "8825 Repairs", "412300", "0", "0", "0"],
  ["5100", "Utilities", "8825 Utilities", "186900", "0", "0", "0"],
  ["5200", "Property management fees", "8825 Other", "164000", "0", "0", "0"],
  ["5300", "Real estate taxes", "8825 Taxes", "380000", "18500", "0", "0"],
  ["5400", "Insurance", "8825 Insurance", "121700", "0", "0", "0"],
  ["5500", "Mortgage interest", "8825 Interest", "512400", "0", "0", "0"],
  ["5600", "Depreciation", "8825 Deprec.", "733500", "0", "0", "0"],
  ["5700", "Professional fees", "8825 Legal/prof.", "48000", "0", "0", "0"],
  ["5800", "Other operating expenses", "8825 Other", "64000", "0", "0", "0"],
];

/** The tax basis the server carries: UTB + AJE + RJE + TJE, as whole dollars (code's, not ours). */
const TAX_BASIS: Readonly<Record<string, string>> = {
  "2050": "-94000",
  "4510": "0",
  "4510-T": "-6200",
  "5300": "398500",
};

/** ATB where it differs from UTB (the server's C8 column; T-05-T37). */
const ADJUSTED: Readonly<Record<string, string>> = { "2050": "-94000", "5300": "398500" };

/** TXP-02's PY column: the TY2024 pre-closing TB, verbatim from the handoff (T-05-T37). */
const PRIOR_YEAR: Readonly<Record<string, string>> = {
  "1000": "463067",
  "1100": "90200",
  "1200": "225600",
  "1300": "148500",
  "1500": "3600000",
  "1600": "15040000",
  "1650": "-1891667",
  "2000": "-112800",
  "2050": "-88400",
  "2100": "-114500",
  "2500": "-11400000",
  "3000": "-5129900",
  "3100": "0",
  "3200": "560000",
  "4000": "-3549900",
  "4100": "-90600",
  "4500": "-17300",
  "4510": "-5800",
  "4510-T": "0",
  "5000": "387600",
  "5100": "175700",
  "5200": "154200",
  "5300": "374600",
  "5400": "114400",
  "5500": "481700",
  "5600": "480000",
  "5700": "45100",
  "5800": "60200",
};

type Group = NonNullable<WorkbookTbRowOut["group"]>;

/** The server's sections (`entity_tb.group_of`): Schedule L 1–14 assets, 15–20 liabilities, 21 and
 * M-2 equity; Form 8825 rents, Schedule K and M-3 income; other mapped lines deductions. */
function groupOf(line: string | null): Group {
  if (line === null) return "unmapped";
  const l = /^L(\d{1,2})[a-z]?$/.exec(line);
  if (l !== null) {
    const n = Number(l[1]);
    return n <= 14 ? "assets" : n <= 20 ? "liabilities" : "equity";
  }
  if (line.startsWith("M-2")) return "equity";
  if (line.startsWith("8825 Rents") || line.startsWith("K ") || line.startsWith("M-3")) {
    return "income";
  }
  return "deductions";
}

function tbRow([code, name, line, utb, aje, rje, tje]: Row, unmapped: boolean): WorkbookTbRowOut {
  const mapped = unmapped ? null : line;
  return {
    account_code: code,
    account_name: name,
    form_line_key: mapped,
    unadjusted: utb,
    aje,
    rje,
    tje,
    tax_basis: TAX_BASIS[code] ?? utb,
    adjusted: ADJUSTED[code] ?? utb,
    prior_year: PRIOR_YEAR[code] ?? null,
    group: groupOf(mapped),
  };
}

type Columns = Omit<WorkbookTbTotalOut, "key" | "label">;
const col = (
  prior_year: string,
  unadjusted: string,
  aje: string,
  adjusted: string,
  tje: string,
  tax_basis: string,
): Columns => ({ prior_year, unadjusted, aje, rje: "0", adjusted, tje, tax_basis });

/** The server's section totals on Run 2, verbatim from the handoff's total rows (T-05-T37). */
const TOTALS: Readonly<Record<string, readonly [string, Columns]>> = {
  assets: ["Total assets", col("17675700", "17914500", "0", "17914500", "0", "17914500")],
  liabilities: [
    "Total liabilities",
    col("-11715700", "-11029800", "-18500", "-11048300", "0", "-11048300"),
  ],
  equity: ["Total equity", col("-4569900", "-5610000", "0", "-5610000", "0", "-5610000")],
  income: ["Total income", col("-3663600", "-3897500", "0", "-3897500", "0", "-3897500")],
  deductions: ["Total deductions", col("2273500", "2622800", "18500", "2641300", "0", "2641300")],
  tb_total: ["TB total (debits less credits)", col("0", "0", "0", "0", "0", "0")],
};

/** Run 1 (e, e2): account 1300 unmapped, so Total assets is without its 158,000. */
const RUN1_ASSETS = col("17527200", "17756500", "0", "17756500", "0", "17756500");
const RUN1_UNMAPPED = col("148500", "158000", "0", "158000", "0", "158000");

function total(key: string, run1: boolean): WorkbookTbTotalOut {
  const [label, values] = TOTALS[key] ?? ["", col("0", "0", "0", "0", "0", "0")];
  if (run1 && key === "assets") return { key, label, ...RUN1_ASSETS };
  if (key === "unmapped") return { key, label: "Total unmapped", ...RUN1_UNMAPPED };
  return { key, label, ...values };
}

export type Statement = "full" | "balance_sheet" | "income_statement";

const AMOUNTS = [
  "unadjusted",
  "aje",
  "rje",
  "tje",
  "tax_basis",
  "adjusted",
  "prior_year",
] as const;

/** The server's line view (`entity_tb.by_line`): one row per mapped form line, its accounts'
 * columns summed in whole dollars, in key order. This is the fixture standing in for the server;
 * the screen never sums. */
function byLine(rows: readonly WorkbookTbRowOut[]): WorkbookTbRowOut[] {
  const lines = new Map<string, WorkbookTbRowOut>();
  for (const r of rows) {
    const key = r.form_line_key;
    if (key === null || key === undefined) continue;
    const prev = lines.get(key);
    if (prev === undefined) {
      lines.set(key, { ...r, account_code: key, account_name: key, form_line_key: key });
      continue;
    }
    const next: Record<string, unknown> = { ...prev };
    for (const k of AMOUNTS) {
      next[k] = String(BigInt(prev[k] ?? "0") + BigInt(r[k] ?? "0"));
    }
    lines.set(key, next as unknown as WorkbookTbRowOut);
  }
  return [...lines.values()].sort((a, b) => (a.account_code < b.account_code ? -1 : 1));
}

/** TXP-02: Run 2's 28 accounts; Run 1's snapshot left account 1300 unmapped (e, e2). The
 * statement narrows as the server does (`entity_tb.narrowed`): Schedule L lines, or the rest. */
export function trialBalance(
  snapshot: Snapshot,
  view: "account" | "line" = "account",
  statement: Statement = "full",
  unmappedOnly = false,
): WorkbookTrialBalanceOut {
  const run1 = snapshot === "run1";
  const all = TB.map((r) => tbRow(r, run1 && r[0] === "1300"));
  const rows = all.filter((r) => {
    const line = r.form_line_key ?? "";
    if (unmappedOnly && r.form_line_key !== null) return false;
    if (statement === "balance_sheet") return line.startsWith("L");
    if (statement === "income_statement") return line !== "" && !line.startsWith("L");
    return true;
  });
  const shown = view === "line" ? byLine(rows) : rows;
  const sections = ["assets", "liabilities", "equity", "income", "deductions", "unmapped"].filter(
    (g) => rows.some((r) => r.group === g),
  );
  const keys = statement === "full" && !unmappedOnly ? [...sections, "tb_total"] : sections;
  return {
    view,
    unmapped: run1 ? 1 : 0,
    rows: shown,
    totals: keys.map((k) => total(k, run1)),
  };
}

/** TXP-02's tally strip on the snapshot (T-05-T37): the server's foots and figure cards. */
export function tallies(snapshot: Snapshot): WorkbookTalliesOut {
  const run1 = snapshot === "run1";
  return {
    items: [
      { key: "utb_foot", label: "Unadjusted foots", state: "tie", difference: "0" },
      { key: "atb_foot", label: "Adjusted foots", state: "tie", difference: "0" },
      { key: "ttb_foot", label: "Tax basis foots", state: "tie", difference: "0" },
      {
        key: "unmapped",
        label: "Unmapped accounts",
        state: run1 ? "check" : "tie",
        difference: run1 ? "1" : "0",
      },
    ],
    figures: [
      { key: "gross_rents", label: "Gross rents", amount: "3872900" },
      { key: "total_deductions", label: "Total deductions", amount: "2641300" },
      { key: "net_rental_income", label: "Net rental RE income", amount: "1231600" },
      { key: "book_total_assets", label: "Book total assets", amount: "17914500" },
    ],
  };
}

export const FIGURES = {
  totalAssets: "17914500",
  totalLiabilities: "11048300",
  capitalAndIncome: "6866200",
  bookIncome: "1256200",
  periodIncome: "628100",
  i18: "-94000",
  m2Off: "6200",
  openItems: [1, 1, 2, 4, 1, 2] as const, // = 11, the Issues badge
} as const;

const PARTNERS = [
  ["gp", "Ridgeline GP LLC", "llc_member", null],
  ["shah", "Meera Shah", "limited", null],
  ["psv", "Pell Street Ventures LLC", "llc_member", null],
  ["ps2", "Pell Street II LLC", "llc_member", null],
  ["feld", "Jonah Feld", "limited", "4417"],
] as const;

/** TXP-06 A: two periods split at the 6/30/2025 assignment (percentage interests). */
export function partners(snapshot: Snapshot): WorkbookPartnersOut {
  return {
    version: snapshot === "run1" ? 1 : 2,
    allowed_actions: [
      "workbook.edit",
      "workbook.export",
      "workbook_run.start",
      "tax_ownership.edit",
    ],
    partners: PARTNERS.map(([key, name, kind, tin]) => ({
      id: stableId(`partner:ridgeline:${key}`),
      name,
      kind,
      tin_last4: tin,
    })),
    periods: [
      {
        starts_on: "2025-01-01",
        ends_on: "2025-06-30",
        shares: { gp: "2", shah: "38", psv: "35", feld: "25" },
      },
      {
        starts_on: "2025-07-01",
        ends_on: "2025-12-31",
        shares: { gp: "2", shah: "38", psv: "30", ps2: "5", feld: "25" },
      },
    ],
    transfers: [],
  };
}

/** TXP-00's run history: Run 1 (Sep 8), Run 2 (Sep 10, 3:31 → 4:12 PM), Run 3 (9:50 AM Sep 14). */
export function runs(snapshot: Snapshot): WorkbookRunRowOut[] {
  const all: WorkbookRunRowOut[] = [
    {
      run_id: stableId("workbook-run:ridgeline-1"),
      run_no: 1,
      started_at: "2026-09-08T09:40:00-05:00",
      started_by: "Olivia Brandt",
      state: snapshot === "run1" ? "needs_input" : "succeeded",
    },
    {
      run_id: stableId("workbook-run:ridgeline-2"),
      run_no: 2,
      started_at: "2026-09-10T15:31:00-05:00",
      started_by: "Olivia Brandt",
      state: "succeeded",
    },
    {
      run_id: stableId("workbook-run:ridgeline-3"),
      run_no: 3,
      started_at: "2026-09-14T09:50:00-05:00",
      started_by: "Samuel Ito",
      state: snapshot === "run3" ? "running" : "succeeded",
    },
  ];
  if (snapshot === "idle") return [];
  if (snapshot === "run1") return all.slice(0, 1);
  if (snapshot === "run2") return all.slice(0, 2);
  return all;
}

/** TXP-00's ten task rows (six groups: 1 + 1 + 2 + 3 + 1 + 2). */
export const TASKS = [
  "Import trial balance",
  "Map to Form 1065 lines",
  "Depreciation register — 6 assets + land",
  "Bonus eligibility by acquisition date",
  "Contributions & distributions",
  "§706(d) interim closing — Pell Street transfer 6/30/2025",
  "Capital accounts & Schedule M-2",
  "Apportionment & PTET — IL · CO · NY",
  "Federal K-1s (5)",
  "State K-1s & K-3s",
] as const;
/** TXP-00 B: the three rows running in Run 3 at 9:52 AM (7 of 10 complete). */
export const RUN3_RUNNING = [
  "Capital accounts & Schedule M-2",
  "Federal K-1s (5)",
  "State K-1s & K-3s",
] as const;

const RUN3: AgentRunOut = {
  id: stableId("workbook-run:ridgeline-3"),
  agent: "workbook_agent",
  agent_label: "Workbook agent — Ridgeline 2025 Form 1065",
  state: "running",
  started_at: "2026-09-14T14:50:00Z",
  finished_at: null,
  duration_ms: null,
  initiator_name: "Samuel Ito",
  subject: null,
};

function runItem(seq: number, task: string, running: boolean): RunItemOut {
  return {
    seq,
    kind: "tool_card",
    at: "2026-09-14T14:50:00Z",
    code: "workbook_task",
    outcome: running ? null : "succeeded",
    detail: task,
    actor: null,
    ref_type: null,
    ref_id: null,
  };
}

/** TXP-00 B's ScriptedRunSource script: seven tasks complete, then the three running rows; under
 * `?static=1` the source freezes on the final frame (7 of 10, three running). */
export function run3Script(): ScriptStep[] {
  const done = TASKS.filter((t) => !(RUN3_RUNNING as readonly string[]).includes(t));
  const items = [
    ...done.map((t, i) => runItem(i + 1, t, false)),
    ...RUN3_RUNNING.map((t, i) => runItem(done.length + i + 1, t, true)),
  ];
  const page = (upto: number): RunItemsOut => ({
    run: RUN3,
    items: items.slice(0, upto),
    last_seq: upto,
    next_seq: upto,
    resync: false,
  });
  return [
    { page: page(done.length), afterMs: 0 },
    { page: page(items.length), afterMs: 600 },
  ];
}
