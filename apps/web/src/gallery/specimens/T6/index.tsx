import {
  type CalcStep,
  type GridPayload,
  matchIdOf,
  RecordHeader,
  SegmentedGroup,
  type TableColumn,
  type TableRow,
  type VarianceValue,
  WorkbookLayout,
  type WorkbookTallyItem,
  type WorkbookVM,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useSession } from "../../../app-core/session";
import type { FixtureParams } from "../../fixture-mode";
import { specimenToolbar } from "../firm-toolbar";
import { COPY } from "./copy";

// T6 Workbook / schedule grid, the template board (F-06-T18; docs/screens/T6.md; F-06.md §3 F5):
// a, b and c on the Ridgeline 2025 Form 1065, Workpaper › Capital Accounts. a: every tally pill
// ties, capital by partner with GP and LP tags; b: M-2 off 6,200 linked to Issue 2, By movement
// with each kind of variance cell; c: the agent building the schedule (Pending pills, skeleton
// rows, the running row). The board's own data (canvas `#t6`, `t6data` and `t6tally`), as T10
// keeps its own (DECISIONS.md, F-06-T14): TPL-06 (F-06-T20) draws the seeded capital accounts.
// d (signed off: "✓ OB", "✓ DR", P before R) is F-06-T20's; e (calculation: Calder Family
// Trust's ending capital traced to Capital!H3 in the source workbook) F-06-T19's. Registered for
// /components/screens/T6?st=a|b|c|d|e. Every figure is a server value in this fixture (ADR-050).

export const T6_STATES = ["a", "b", "c", "d", "e"] as const;
export type T6State = (typeof T6_STATES)[number];

const RIDGELINE = "Ridgeline Property Partners, LP";
const AGENT = "Accrued Agent";

const ENTITY_TABS = ["Agent", { label: "Issues", count: 9, bad: true }, "Workpaper", "Review"];
const WORKPAPER_TABS = [
  "Summary",
  "Financials",
  "Fixed Assets",
  "M-1/M-3",
  "Schedule M-2",
  "Schedule K",
  "Capital Accounts",
];

// Calculation is F-06-T19's: the calc tree beside the source workbook.
const VIEWS = [COPY.views.byPartner, COPY.views.byMovement, COPY.views.calculation];

const SOURCE = "Ridgeline capital accounts 2025.xlsx";
const SHEET = "Capital";
const cell = (ref: string): string =>
  matchIdOf({ kind: "sheet_cell", file: SOURCE, sheet: SHEET, cell: ref });

/** T6e's steps: the server's calculation of Calder Family Trust's ending capital. A step's match
 * id is its typed sheet-cell locator (INV-2); a form line has none. */
export const CALC_STEPS: readonly CalcStep[] = [
  {
    ref: "end",
    depth: 0,
    op: "",
    label: "Ending capital",
    value: "938,561",
    src: "Capital!H3",
    match: cell("H3"),
  },
  {
    ref: "beg",
    depth: 1,
    op: "",
    label: "Beginning capital",
    value: "882,824",
    src: "Capital!D3",
    match: cell("D3"),
  },
  {
    ref: "con",
    depth: 1,
    op: "+",
    label: "Capital contributed",
    value: "—",
    src: "Capital!E3",
    match: cell("E3"),
  },
  {
    ref: "inc",
    depth: 1,
    op: "+",
    label: "Share of income",
    value: "204,237",
    src: "Capital!F3",
    match: cell("F3"),
  },
  {
    ref: "pni",
    depth: 2,
    op: "",
    label: "Partnership net income",
    value: "412,600",
    src: "Capital!F6",
    match: cell("F6"),
  },
  {
    ref: "rre",
    depth: 3,
    op: "",
    label: "Net rental real estate income",
    value: "384,120",
    src: "Form 8825 · line 21",
  },
  {
    ref: "int",
    depth: 3,
    op: "+",
    label: "Interest income",
    value: "28,480",
    src: "Schedule K · line 5",
  },
  {
    ref: "share",
    depth: 2,
    op: "×",
    label: "Profit share",
    value: "49.5%",
    src: "Capital!C3",
    match: cell("C3"),
  },
  {
    ref: "dist",
    depth: 1,
    op: "−",
    label: "Distributions",
    value: "(148,500)",
    src: "Capital!G3",
    match: cell("G3"),
  },
];

const GRID_HEAD = [
  "Partner",
  "Type",
  "Share",
  "Beginning",
  "Contributed",
  "Income",
  "Distributions",
  "Ending",
];
const GRID_KEYS = ["a", "b", "c", "d", "e", "f", "g", "h"] as const;
const GRID_ROWS: readonly (readonly string[])[] = [
  GRID_HEAD,
  ["Ridgeline GP, LLC", "GP", "1.0%", "17,835", "", "4,126", "(3,000)", "18,961"],
  ["Calder Family Trust", "LP", "49.5%", "882,824", "", "204,237", "(148,500)", "938,561"],
  [
    "Marrow Point Holdings, LLC",
    "LP",
    "29.5%",
    "486,127",
    "40,000",
    "121,717",
    "(88,500)",
    "559,344",
  ],
  ["Juno Okafor", "LP", "20.0%", "356,696", "", "82,520", "(60,000)", "379,216"],
  ["Total", "", "100.0%", "1,743,482", "40,000", "412,600", "(300,000)", "1,896,082"],
];

/** T6e's source workbook, as the evidence pipeline renders the .xlsx (values, not formulas). */
export const SOURCE_GRID: GridPayload = {
  label: SOURCE,
  source: SOURCE,
  sheet: SHEET,
  headerRow: true,
  cite: "H3",
  columns: [
    { key: "a", width: 212 },
    { key: "b", width: 46, align: "left" },
    { key: "c", width: 62, align: "right" },
    { key: "d", width: 100, align: "right" },
    { key: "e", width: 92, align: "right" },
    { key: "f", width: 92, align: "right" },
    { key: "g", width: 108, align: "right" },
    { key: "h", width: 100, align: "right" },
  ],
  rows: GRID_ROWS.map((r, i) => ({
    id: `r${String(i + 1)}`,
    cells: Object.fromEntries(GRID_KEYS.map((k, c) => [k, r[c] ?? null])),
  })),
  footer: { cell: "H3", value: "938,561", meta: COPY.sheetMeta },
};

const PARTNER_COLUMNS: TableColumn[] = [
  { key: "name", header: "Partner", type: "label" },
  { key: "beg", header: "Beginning", width: 120 },
  { key: "con", header: "Contributed", width: 120 },
  { key: "inc", header: "Income", width: 120 },
  { key: "dist", header: "Distributions", width: 120 },
  { key: "end", header: "Ending", width: 120 },
];

const PK = ["beg", "con", "inc", "dist", "end"] as const;

function partner(
  id: string,
  label: string,
  values: readonly string[],
  extra: Partial<TableRow> = {},
): TableRow {
  return {
    id,
    label,
    cells: Object.fromEntries(PK.map((k, i) => [k, { value: values[i] ?? null }])),
    ...extra,
  };
}

export const PARTNER_ROWS: TableRow[] = [
  { id: "gp-band", kind: "group", label: "General partner", cells: {} },
  partner("gp", "Ridgeline GP, LLC", ["17835", "0", "4126", "-3000", "18961"], {
    indent: 1,
    tag: "GP",
  }),
  { id: "lp-band", kind: "group", label: "Limited partners", cells: {} },
  partner("cft", "Calder Family Trust", ["882824", "0", "204237", "-148500", "938561"], {
    indent: 1,
    tag: "LP",
  }),
  partner("mph", "Marrow Point Holdings, LLC", ["486127", "40000", "121717", "-88500", "559344"], {
    indent: 1,
    tag: "LP",
  }),
  partner("jo", "Juno Okafor", ["356696", "0", "82520", "-60000", "379216"], {
    indent: 1,
    tag: "LP",
  }),
  partner("lpt", "Total limited partners", ["1725647", "40000", "408474", "-297000", "1877121"], {
    kind: "total",
  }),
  partner("tpc", "Total partners’ capital", ["1743482", "40000", "412600", "-300000", "1896082"], {
    kind: "grand",
  }),
];

const MOVE_COLUMNS: TableColumn[] = [
  { key: "name", header: RIDGELINE, type: "label", entity: true },
  { key: "y24", header: "2024", width: 120 },
  { key: "y25", header: "2025", width: 120 },
  { key: "d", header: "Change", type: "variance", width: 220 },
];

function movement(
  id: string,
  label: string,
  y24: string,
  y25: string,
  variance: VarianceValue,
  extra: Partial<TableRow> = { indent: 1 },
): TableRow {
  return {
    id,
    label,
    cells: { y24: { value: y24 }, y25: { value: y25 }, d: { value: null, variance } },
    ...extra,
  };
}

/** T6b's By movement: every variance state once (the canvas's `move(true)`). Δ, Δ% and the
 * thresholds are the server's. */
export const MOVE_ROWS_OFF: TableRow[] = [
  movement("beg", "Beginning capital", "1602240", "1743482", {
    value: "141242",
    ratio: "0.0882",
    threshold: "100000",
    explained: { text: "Equals the 2024 ending capital on the filed return.", by: AGENT },
  }),
  movement("con", "Capital contributed", "0", "40000", {
    value: "40000",
    ratio: null,
    threshold: "25000",
  }),
  movement("rre", "Net rental real estate income", "361900", "384120", {
    value: "22220",
    ratio: "0.0614",
    threshold: "25000",
  }),
  movement("int", "Interest income", "29342", "28480", {
    value: "-862",
    ratio: "-0.0294",
    threshold: "25000",
  }),
  movement("dist", "Distributions", "-250000", "-300000", {
    value: "-50000",
    ratio: "-0.2",
    threshold: "25000",
    exception: { issue: "2" },
  }),
  movement(
    "end",
    "Ending capital",
    "1743482",
    "1896082",
    { value: "152600", ratio: "0.0875", threshold: "100000", posted: true },
    { kind: "grand" },
  ),
];

const head: WorkbookTallyItem[] = [
  { label: COPY.tally.beginning, value: "1,743,482", info: COPY.info.beginning },
  { label: COPY.tally.ending, value: "1,896,082", info: COPY.info.ending },
  { label: COPY.tally.capitalFoots, tally: "tie" },
];

export function t6Tally(state: T6State): WorkbookTallyItem[] {
  if (state === "c") {
    return [
      { label: COPY.tally.beginning, running: COPY.building },
      { label: COPY.tally.ending, running: COPY.building },
      { label: COPY.tally.capitalFoots, tally: "pending" },
      { label: COPY.tally.m2Ties, tally: "pending" },
      { label: COPY.tally.schLEquity, tally: "pending" },
      { label: COPY.tally.k1ItemL, tally: "pending" },
    ];
  }
  return [
    ...head,
    state === "b"
      ? { label: COPY.tally.m2Ties, tally: "off", vars: { amount: "6,200" }, issue: "2" }
      : { label: COPY.tally.m2Ties, tally: "tie" },
    { label: COPY.tally.schLEquity, tally: "tie" },
    { label: COPY.tally.k1ItemL, tally: "tie" },
  ];
}

const VIEW_OF: Record<T6State, string> = {
  a: COPY.views.byPartner,
  b: COPY.views.byMovement,
  c: COPY.views.byPartner,
  d: COPY.views.byPartner,
  e: COPY.views.calculation,
};

/** T6d: Olivia Brandt prepared (L1), Daniel Reyes reviewed (L2); P before R. */
export const T6_SIGN_OFFS = [
  { level: "L2", initials: "DR", name: "Daniel Reyes", when: "Sep 14, 9:40 AM" },
  { level: "L1", initials: "OB", name: "Olivia Brandt", when: "Sep 10, 4:12 PM" },
] as const;

export function t6Workbook(state: T6State, view: string = VIEW_OF[state]): WorkbookVM {
  const byMovement = view === COPY.views.byMovement && state !== "c";
  if (view === COPY.views.calculation && state !== "c") {
    return {
      views: VIEWS,
      view,
      title: COPY.title,
      tally: [],
      panes: [
        { kind: "calc", width: 452, title: COPY.calcTitle, tree: CALC_STEPS },
        { kind: "grid", grid: SOURCE_GRID },
      ],
    };
  }
  return {
    views: VIEWS,
    view,
    title: COPY.title,
    tally: t6Tally(state),
    panes: [
      {
        kind: "statement",
        table: byMovement
          ? {
              label: COPY.tables.byMovement,
              columns: MOVE_COLUMNS,
              rows: MOVE_ROWS_OFF,
              footnote: COPY.footnote.byMovement,
            }
          : {
              label: COPY.tables.byPartner,
              columns: PARTNER_COLUMNS,
              rows: PARTNER_ROWS,
              footnote: COPY.footnote.byPartner,
            },
      },
    ],
    ...(state === "c" ? { building: { label: COPY.running } } : {}),
    ...(state === "d" ? { signOffs: T6_SIGN_OFFS } : {}),
  };
}

export const SIGN_OFF_TARGET = "workpaper:ridgeline-2025-capital-accounts";

export function T6Board({
  state,
  onOpenIssue,
  onOpenSignOff,
}: {
  state: T6State;
  onOpenIssue?: (issue: string) => void;
  /** SHL-12 (P-04): the chips and Sign off… only hand off; nothing here signs. */
  onOpenSignOff?: (target: string, level?: string) => void;
}): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const [view, setView] = useState(VIEW_OF[state]);
  return (
    <WorkbookLayout
      frame
      height={860}
      workbook={t6Workbook(state, view)}
      copy={{
        openInExcel: COPY.openInExcel,
        download: COPY.download,
        signOff: COPY.signOff,
        views: COPY.viewsLabel,
        scroller: COPY.scroller,
        signOffChips: {
          label: COPY.signOffs,
          changedAfter: COPY.changedAfterSignOff,
          open: COPY.openSignOff,
        },
      }}
      {...(state === "d"
        ? {
            signOff: { actor: { kind: "human", name: "Daniel Reyes" }, target: SIGN_OFF_TARGET },
            onOpenSignOff: onOpenSignOff ?? (() => undefined),
          }
        : {})}
      toolbar={specimenToolbar(firm, "Tax Returns")}
      record={
        <RecordHeader
          title="2025 Form 1065"
          context={RIDGELINE}
          state="In review · Partner"
          checkpoints
          sync="synced"
          syncDate="Sep 11"
          assistant
        />
      }
      tabs={
        <SegmentedGroup
          size="small"
          label="Partnership return"
          options={ENTITY_TABS}
          active="Workpaper"
          sub={{ Workpaper: { options: WORKPAPER_TABS, active: "Capital Accounts" } }}
        />
      }
      onView={setView}
      onOpenInExcel={() => undefined}
      onDownload={() => undefined}
      onOpenIssue={onOpenIssue ?? (() => undefined)}
      onExplain={() => undefined}
    />
  );
}

export function T6Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: T6State = T6_STATES.find((s) => s === params.st) ?? "a";
  const [opened, setOpened] = useState<string | null>(null);
  const [signOff, setSignOff] = useState<string | null>(null);
  return (
    <div
      data-artboard={state}
      {...(opened === null ? {} : { "data-opened-issue": opened })}
      {...(signOff === null ? {} : { "data-opened-sign-off": signOff })}
    >
      <T6Board
        state={state}
        onOpenIssue={setOpened}
        onOpenSignOff={(target, level) => {
          setSignOff(`${target}:${level ?? ""}`);
        }}
      />
    </div>
  );
}
