import {
  amount,
  RecordHeader,
  SegmentedGroup,
  type TableColumn,
  type TableRow,
  WorkbookLayout,
  type WorkbookPaneVM,
  type WorkbookTallyItem,
  type WorkbookVM,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useSession } from "../../../app-core/session";
import {
  CAPITAL_ROWS,
  CAPITAL_TOTAL,
  type CapitalRow,
  RIDGELINE,
  RIDGELINE_OPEN_ISSUES,
  TALLY_DRAFTED,
  TALLY_FIXED,
  TIE_OUT,
  type TallyItem,
} from "../../../fixtures/seed/tax";
import type { FixtureParams } from "../../fixture-mode";
import { specimenToolbar } from "../firm-toolbar";
import { COPY as T6_COPY } from "../T6/copy";
import { COPY } from "./copy";

// TPL-06 Workbook grid specimen, Ridgeline capital accounts (F-06-T20; docs/screens/TPL-06.md):
// the 2025 Form 1065 capital rollforward on the T6 WorkbookLayout, viewer Samuel Ito at E0.
// a as drafted (M-2 off 6,200, the only amber element); b fixed (the tax-exempt column, Ending
// 6,866,200); c by partner (five 452 panes, Tax beside Book); d building; e signed off ("✓ SI",
// "Reviewed · SI"). Every figure is the seed's (fixtures/seed/tax/ridgeline.ts), proven to foot
// by tax.foot.test.ts; the kit formats and never adds (ADR-050). Registered for
// /components/screens/TPL-06?st=a…e.

export const TPL06_STATES = ["a", "b", "c", "d", "e"] as const;
export type Tpl06State = (typeof TPL06_STATES)[number];

const SAMUEL = "Samuel Ito";
const TARGET = "workpaper:ridgeline-2025-capital-accounts";
const ISSUE = TIE_OUT.issueRef.replace(/\D/g, "");
const GROUP_A = [
  "Agent",
  { label: "Issues", count: RIDGELINE_OPEN_ISSUES, bad: true },
  "Workpaper",
  "Review",
  "Intake",
  "Activity",
];
const GROUP_B = [
  "Summary",
  "Financials",
  "Fixed Assets",
  "M-1/M-3",
  "Schedule M-2",
  "Schedule K",
  "Capital Accounts",
  "Basis",
  "States",
];
const VIEWS = [COPY.views.byPartner, COPY.views.byMovement];

const whole = (v: string): string => amount(v, "whole").text;
const fixedState = (state: Tpl06State): boolean => state === "b" || state === "e";

function tally(state: Tpl06State): WorkbookTallyItem[] {
  const items: readonly TallyItem[] = fixedState(state) ? TALLY_FIXED : TALLY_DRAFTED;
  return items.map((t): WorkbookTallyItem => {
    const label = COPY.tally[t.key as keyof typeof COPY.tally];
    if (t.result === "off") {
      return { label, tally: "off", vars: { amount: whole(t.difference ?? "0") }, issue: ISSUE };
    }
    if (t.result !== undefined) return { label, tally: t.result };
    return { label, value: amount(t.value ?? "0", "whole", { zero: "explicit" }).text };
  });
}

function movementColumns(fixed: boolean): TableColumn[] {
  return [
    { key: "partner", header: COPY.columns.partner, type: "label", width: 280 },
    { key: "interest", header: COPY.columns.interest, type: "text", width: 130, align: "right" },
    { key: "beginning", header: COPY.columns.beginning, width: 140 },
    { key: "contributions", header: COPY.columns.contributions, width: 130 },
    { key: "income", header: COPY.columns.income, width: 160 },
    ...(fixed ? [{ key: "taxExempt", header: COPY.columns.taxExempt, width: 130 }] : []),
    { key: "transfers", header: COPY.columns.transfers, width: 130 },
    { key: "distributions", header: COPY.columns.distributions, width: 130 },
    {
      key: "ending",
      header: fixed ? COPY.columns.endingFixed : COPY.columns.endingDrafted,
      width: 150,
    },
  ];
}

function movementCells(
  r: Pick<CapitalRow, "beginning" | "contributions" | "income" | "taxExempt" | "transfers">,
  rest: { interest: string; distributions: string; ending: string },
  fixed: boolean,
): TableRow["cells"] {
  return {
    interest: { value: rest.interest },
    beginning: { value: r.beginning },
    contributions: { value: r.contributions },
    income: { value: r.income },
    ...(fixed ? { taxExempt: { value: r.taxExempt } } : {}),
    transfers: { value: r.transfers },
    distributions: { value: rest.distributions },
    ending: { value: rest.ending },
  };
}

export function movementRows(state: Tpl06State): TableRow[] {
  const fixed = fixedState(state);
  const partners: TableRow[] = CAPITAL_ROWS.map((r, i) => ({
    id: `p${String(i)}`,
    label: r.partner,
    tag: r.tag,
    cells: movementCells(
      r,
      {
        interest: `${r.interest[0]} · ${r.interest[1]}`,
        distributions: r.distributions,
        ending: fixed ? r.endingFixed : r.endingDrafted,
      },
      fixed,
    ),
  }));
  const ending = fixed ? CAPITAL_TOTAL.endingFixed : CAPITAL_TOTAL.endingDrafted;
  const total: TableRow = {
    id: "total",
    kind: "total",
    label: COPY.total,
    cells: movementCells(
      CAPITAL_TOTAL,
      { interest: CAPITAL_TOTAL.interest, distributions: CAPITAL_TOTAL.distributions, ending },
      fixed,
    ),
  };
  const tieOut: TableRow[] = [
    { id: "tie-band", kind: "group", label: COPY.tieOutBand, cells: {} },
    { id: "tie-m2", label: COPY.tieOut.m2, indent: 1, cells: { ending: { value: ending } } },
    {
      id: "tie-l",
      label: COPY.tieOut.scheduleL,
      indent: 1,
      cells: { ending: { value: TIE_OUT.scheduleL } },
    },
    {
      id: "tie-diff",
      label: COPY.tieOut.difference,
      indent: 1,
      cells: { ending: { value: fixed ? "0" : TIE_OUT.differenceDrafted } },
    },
    ...(fixed
      ? []
      : [{ id: "tie-cause", label: `${COPY.taxExemptLink} →`, indent: 1, cells: {} }]),
  ];
  return [...partners, total, ...tieOut];
}

const PARTNER_COLUMNS: TableColumn[] = [
  { key: "line", header: "", type: "label" },
  { key: "tax", header: COPY.columns.tax, width: 120 },
  { key: "book", header: COPY.columns.book, width: 120 },
];

/** One partner's pane (TPL-06c): Tax beside Book, identical on the income-tax basis. */
export function partnerRows(r: CapitalRow): TableRow[] {
  const both = (value: string): TableRow["cells"] => ({ tax: { value }, book: { value } });
  const b = COPY.byPartnerBands;
  return [
    { id: "beg", label: b.beginning, cells: both(r.beginning) },
    { id: "con-band", kind: "group", label: b.contributions, cells: {} },
    { id: "con", label: b.contributions, indent: 1, cells: both(r.contributions) },
    { id: "inc-band", kind: "group", label: b.income, cells: {} },
    { id: "alloc", label: b.allocated, indent: 1, cells: both(r.income) },
    { id: "exempt", label: b.taxExempt, indent: 1, cells: both(r.taxExempt) },
    { id: "oth-band", kind: "group", label: b.other, cells: {} },
    { id: "xfer", label: b.transfers, indent: 1, cells: both(r.transfers) },
    { id: "dist-band", kind: "group", label: b.distributions, cells: {} },
    { id: "dist", label: b.distributions, indent: 1, cells: both(r.distributions) },
    { id: "end", kind: "grand", label: b.ending, cells: both(r.endingFixed) },
  ];
}

export function tpl06Workbook(state: Tpl06State, view?: string): WorkbookVM {
  const byPartner =
    (view ?? (state === "c" ? COPY.views.byPartner : COPY.views.byMovement)) ===
    COPY.views.byPartner;
  const panes: WorkbookPaneVM[] = byPartner
    ? CAPITAL_ROWS.map((r) => ({
        kind: "statement",
        width: 452,
        title: r.partner,
        table: { label: r.partner, columns: PARTNER_COLUMNS, rows: partnerRows(r) },
      }))
    : [
        {
          kind: "statement",
          title: COPY.paneTitle,
          table: {
            label: COPY.paneTitle,
            columns: movementColumns(fixedState(state)),
            rows: movementRows(state),
            footnote: COPY.transfersFootnote,
          },
        },
      ];
  return {
    views: VIEWS,
    view: byPartner ? COPY.views.byPartner : COPY.views.byMovement,
    title: COPY.viewTitle,
    tally: tally(state),
    panes,
    ...(state === "d" ? { building: { label: COPY.running } } : {}),
    ...(state === "e"
      ? { signOffs: [{ level: "L2", initials: "SI", name: SAMUEL, when: "Sep 14, 9:24 AM" }] }
      : {}),
  };
}

export function Tpl06Board({
  state,
  onOpenIssue,
  onOpenSignOff,
}: {
  state: Tpl06State;
  onOpenIssue?: (issue: string) => void;
  onOpenSignOff?: (target: string, level?: string) => void;
}): JSX.Element {
  const firm = useSession().tenant?.firm_name ?? "";
  const [view, setView] = useState<string | undefined>(undefined);
  return (
    <WorkbookLayout
      frame
      height={860}
      workbook={tpl06Workbook(state, view)}
      copy={{
        openInExcel: COPY.openInExcel,
        download: T6_COPY.download,
        signOff: COPY.signOff,
        views: T6_COPY.viewsLabel,
        scroller: T6_COPY.scroller,
        signOffChips: {
          label: T6_COPY.signOffs,
          changedAfter: T6_COPY.changedAfterSignOff,
          open: T6_COPY.openSignOff,
          reviewed: COPY.reviewed,
        },
      }}
      toolbar={specimenToolbar(firm, "Tax Returns")}
      record={
        <RecordHeader
          title="2025 Form 1065"
          context={RIDGELINE}
          state="In review · Partner"
          checkpoints
          sync="not_yet_exported"
          assistant
        />
      }
      tabs={
        <SegmentedGroup
          size="small"
          label="Partnership return"
          options={GROUP_A}
          active="Review"
          sub={{ Review: { options: GROUP_B, active: "Capital Accounts" } }}
        />
      }
      signOff={{ actor: { kind: "human", name: SAMUEL }, target: TARGET, level: "L2" }}
      onView={setView}
      onOpenInExcel={() => undefined}
      onDownload={() => undefined}
      onOpenIssue={onOpenIssue ?? (() => undefined)}
      onOpenSignOff={onOpenSignOff ?? (() => undefined)}
    />
  );
}

export function Tpl06Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: Tpl06State = TPL06_STATES.find((s) => s === params.st) ?? "a";
  const [issue, setIssue] = useState<string | null>(null);
  const [signOff, setSignOff] = useState<string | null>(null);
  return (
    <div
      data-artboard={state}
      {...(issue === null ? {} : { "data-opened-issue": issue })}
      {...(signOff === null ? {} : { "data-opened-sign-off": signOff })}
    >
      <Tpl06Board
        state={state}
        onOpenIssue={setIssue}
        onOpenSignOff={(target, level) => {
          setSignOff(`${target}:${level ?? ""}`);
        }}
      />
    </div>
  );
}
