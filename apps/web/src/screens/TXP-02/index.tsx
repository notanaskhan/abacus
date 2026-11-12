// TXP-02 · Review › Financials (TB → TTB) (T-05-T37; docs/screens/TXP-02.md; handoff TXP-02 A–F):
// T6 inside the entity return's layout: the control bar (two small Segmented controls, Open in
// Excel, + Journal entry…), the tally strip and the full-width TB pane in the TB grammar ("$" on
// every cell, whole dollars, credits in parentheses). Every figure, section total and tie is the
// server's (`GET …/trial-balance`, `…/tallies`; ADR-050): the screen formats and lays out and adds
// nothing. E: an unmapped account reads "Map…" and the Unmapped card "Check"; F: Building, tallies
// Pending and skeleton rows under the running row.
import type {
  WorkbookTalliesOut,
  WorkbookTbRowOut,
  WorkbookTbTotalOut,
  WorkbookTrialBalanceOut,
} from "@abacus/api-client";
import {
  Button,
  DataGrid,
  Segmented,
  SkeletonRows,
  Spinner,
  type TableColumn,
  type TableRow,
  type TallyItem,
  TallyStrip,
  amount,
} from "@abacus/ui";
import type { JSX } from "react";
import { COPY } from "./copy";

export type Txp02View = "account" | "line";
export type Txp02Statement = "full" | "balance_sheet" | "income_statement";

const MONEY = { type: "num", width: 128, format: "dollars" } as const;
export const COLUMNS: readonly TableColumn[] = [
  { key: "code", header: COPY.columns.code, type: "text", width: 56 },
  { key: "name", header: COPY.columns.name, type: "label", width: 200 },
  { key: "line", header: COPY.columns.line, type: "text", width: 92 },
  { key: "py", header: COPY.columns.py, ...MONEY },
  { key: "utb", header: COPY.columns.utb, ...MONEY },
  { key: "aje", header: COPY.columns.aje, ...MONEY },
  { key: "rje", header: COPY.columns.rje, ...MONEY },
  { key: "atb", header: COPY.columns.atb, ...MONEY },
  { key: "tje", header: COPY.columns.tje, ...MONEY },
  { key: "ttb", header: COPY.columns.ttb, ...MONEY },
];

const GROUP_ORDER = [
  "assets",
  "liabilities",
  "equity",
  "income",
  "deductions",
  "unmapped",
] as const;

type Money = string | null | undefined;
const v = (value: Money) => ({ value: value ?? null });

function amounts(r: {
  prior_year?: Money;
  unadjusted: string;
  aje: string;
  rje: string;
  adjusted?: Money;
  tje: string;
  tax_basis: string;
}) {
  return {
    py: v(r.prior_year),
    utb: v(r.unadjusted),
    aje: v(r.aje),
    rje: v(r.rje),
    atb: v(r.adjusted),
    tje: v(r.tje),
    ttb: v(r.tax_basis),
  };
}

function itemRow(r: WorkbookTbRowOut, view: Txp02View): TableRow {
  const mapped = r.form_line_key ?? null;
  return {
    id: `acct:${r.account_code}`,
    label: r.account_name,
    cells: {
      code: { value: view === "line" ? null : r.account_code },
      line: { value: mapped ?? COPY.map },
      ...amounts(r),
    },
  };
}

function totalRow(t: WorkbookTbTotalOut): TableRow {
  return {
    id: `total:${t.key}`,
    kind: t.key === "tb_total" ? "grand" : "total",
    label: t.label,
    cells: amounts(t),
  };
}

/** The table in the server's order: each section's group row, its rows, its total; then the TB
 * total. Rows without a section (an older server) fall under no group. */
export function tableRows(tb: WorkbookTrialBalanceOut): TableRow[] {
  const out: TableRow[] = [];
  const totals = new Map((tb.totals ?? []).map((t) => [t.key, t]));
  for (const g of GROUP_ORDER) {
    const rows = tb.rows.filter((r) => (r.group ?? null) === g);
    if (rows.length === 0) continue;
    out.push({ id: `group:${g}`, kind: "group", label: COPY.groups[g], cells: {} });
    for (const r of rows) out.push(itemRow(r, tb.view));
    const total = totals.get(g);
    if (total !== undefined) out.push(totalRow(total));
  }
  for (const r of tb.rows)
    if (r.group === undefined || r.group === null) out.push(itemRow(r, tb.view));
  const grand = totals.get("tb_total");
  if (grand !== undefined) out.push(totalRow(grand));
  return out;
}

/** The tally strip: the server's tax-basis foot and unmapped count, then its figure cards. */
export function tallyItems(
  t: WorkbookTalliesOut | undefined,
  building: boolean,
  onUnmapped?: () => void,
): TallyItem[] {
  const pending = { pill: { text: COPY.pending, variant: "neutral" as const } };
  const foot = t?.items.find((i) => i.key === "ttb_foot");
  const unmapped = t?.items.find((i) => i.key === "unmapped");
  const figure = (key: keyof typeof COPY.cards): TallyItem => {
    const found = t?.figures?.find((f) => f.key === key);
    const info = (COPY.info as Readonly<Record<string, string>>)[key];
    if (building || found === undefined) return { label: COPY.cards[key], ...pending };
    return {
      label: COPY.cards[key],
      value: amount(found.amount, "dollars").text,
      ...(info === undefined ? {} : { info }),
    };
  };
  return [
    building || foot === undefined
      ? { label: COPY.cards.ttb, ...pending }
      : { label: COPY.cards.ttb, tally: foot.state === "tie" ? "tie" : "off" },
    building || unmapped === undefined
      ? { label: COPY.cards.unmapped, ...pending }
      : unmapped.state === "check"
        ? {
            label: COPY.cards.unmapped,
            value: String(Number(unmapped.difference ?? "0")),
            pill: { text: "Check", variant: "amber" },
            ...(onUnmapped === undefined
              ? {}
              : { link: { text: COPY.showUnmapped, onClick: onUnmapped } }),
          }
        : { label: COPY.cards.unmapped, value: "0" },
    figure("gross_rents"),
    figure("total_deductions"),
    figure("net_rental_income"),
    figure("book_total_assets"),
  ];
}

const VIEW_LABEL: Readonly<Record<Txp02View, string>> = {
  account: COPY.byAccount,
  line: COPY.byLine,
};
const STATEMENT_LABEL: Readonly<Record<Txp02Statement, string>> = {
  full: COPY.full,
  balance_sheet: COPY.balanceSheet,
  income_statement: COPY.incomeStatement,
};

function statementOf(label: string): Txp02Statement {
  if (label === COPY.balanceSheet) return "balance_sheet";
  if (label === COPY.incomeStatement) return "income_statement";
  return "full";
}

export interface TXP02Props {
  tb?: WorkbookTrialBalanceOut | undefined;
  tallies?: WorkbookTalliesOut | undefined;
  view: Txp02View;
  statement: Txp02Statement;
  /** `import_trial_balance` is running (F). */
  building?: boolean;
  onView?: (view: Txp02View) => void;
  onStatement?: (statement: Txp02Statement) => void;
  /** The Unmapped card filters to unmapped rows. */
  onUnmapped?: () => void;
  /** "Map…" or an export code: the line picker (O1) for the account. */
  onMap?: (accountCode: string) => void;
  /** Any row: SHL-09 for its cells (the screen passes the account). */
  onOpenRow?: (accountCode: string) => void;
  onOpenInExcel?: () => void;
  onJournalEntry?: () => void;
}

export function TXP02({
  tb,
  tallies,
  view,
  statement,
  building = false,
  onUnmapped,
  onView,
  onStatement,
  onMap,
  onOpenRow,
  onOpenInExcel,
  onJournalEntry,
}: TXP02Props): JSX.Element {
  const rows = tb === undefined ? [] : tableRows(tb);
  return (
    <div data-screen="TXP-02" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]">
        <Segmented
          size="small"
          label={COPY.views}
          options={[COPY.byAccount, COPY.byLine]}
          active={VIEW_LABEL[view]}
          {...(onView === undefined
            ? {}
            : { onChange: (label: string) => onView(label === COPY.byLine ? "line" : "account") })}
        />
        <Segmented
          size="small"
          label={COPY.statements}
          options={[COPY.full, COPY.balanceSheet, COPY.incomeStatement]}
          active={STATEMENT_LABEL[statement]}
          {...(onStatement === undefined
            ? {}
            : { onChange: (label: string) => onStatement(statementOf(label)) })}
        />
        {building ? <Spinner size={12} label={COPY.building} showLabel /> : null}
        <span className="flex-1" />
        <Button variant="ghost" size="sm" icon="square-arrow-out-up-right" onClick={onOpenInExcel}>
          {COPY.openInExcel}
        </Button>
        <Button variant="secondary" size="sm" onClick={onJournalEntry}>
          {COPY.journalEntry}
        </Button>
      </div>
      <TallyStrip
        label={COPY.tally}
        items={tallyItems(tallies, building, onUnmapped)}
        className="flex-none px-[12px] pb-[10px]"
      />
      <div className="min-h-0 flex-1 overflow-auto px-[12px] pb-[12px]">
        {building || tb === undefined ? (
          <SkeletonRows type="table" immediate label={COPY.building} />
        ) : (
          <>
            <DataGrid
              label={COPY.table}
              grammar="ledger"
              columns={COLUMNS}
              rows={rows}
              onOpen={(row) => {
                const code = row.id.startsWith("acct:") ? row.id.slice(5) : null;
                if (code === null) return;
                const mapped = tb.rows.find((r) => r.account_code === code)?.form_line_key;
                if ((mapped ?? null) === null) onMap?.(code);
                else onOpenRow?.(code);
              }}
            />
            <p className="mt-[8px] text-[11.5px] text-ink-3">{COPY.footnote}</p>
          </>
        )}
      </div>
    </div>
  );
}
