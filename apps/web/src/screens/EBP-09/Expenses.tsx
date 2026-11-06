import type {
  ComplianceTestOut,
  ExpenseRowOut,
  ExpensesOut,
  FiguresOut,
  QualificationFactOut,
} from "@abacus/api-client";
import {
  ebpBudgetAccountOptions,
  ebpComplianceTestsOptions,
  ebpPlanExpensesOptions,
  ebpPlanQualificationOptions,
} from "@abacus/api-client/query";
import {
  type CockpitCanvas,
  Button,
  PaneAction,
  Pill,
  Segmented,
  Skeleton,
  amount,
  cn,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// EBP-09 · Administrative expenses & operational compliance (A-05-T45; A-05 F8; the handoff spec):
// the Testing › Admin Expenses & Compliance canvas, a spreadsheet grid in T6's grammar. Figures are
// the server's (A-05-T43). A cell's citations show in the Sheet!Cell footer; each tally says which
// tab its exception count covers; only a person raises an exception or signs off.

export const ADMIN_EXPENSES = "ebp_09";
const FLAG = "ebp.modules";
type Tab = keyof typeof COPY.tabs;
const TABS: readonly Tab[] = ["expenses", "compliance", "qualification"];
const CARD =
  "flex min-w-0 flex-1 flex-col justify-center rounded-[10px] bg-card e1 px-[12px] py-[4px]";
const LABEL = "text-[11px] uppercase text-ink-3";
const GRID = "h-[28px] border-[0.5px] border-hair px-[6px] text-[11.5px]";
const NUM = "w-[34px] border-[0.5px] border-hair bg-faint text-center text-[11px] text-ink-3";

const money = (v: string | null | undefined): string =>
  v === null || v === undefined ? "" : amount(v, "cents", { zero: "explicit" }).text;

export interface ExpensesOptions {
  active?: boolean;
  tab?: Tab;
  onTab?: (tab: Tab) => void;
  signedInitials?: string | null;
  onSignOff?: () => void;
  onSourceDocs?: () => void;
  onRaise?: () => void;
  /** The row-number menu's Request TPA support: SHL-14, which sends nothing. */
  onRequestSupport?: (expenseId: string) => void;
  /** EBP-03, EBP-05 and EBP-07 references open those screens. */
  onReference?: (screen: string) => void;
}

function Tally({
  items,
  scope,
}: {
  items: readonly { key: string; label: string; value: string }[];
  scope: string;
}): JSX.Element {
  return (
    <div
      data-ebp09="tally"
      data-scope={scope}
      className="flex h-[52px] items-center gap-[8px] px-[12px]"
    >
      {items.map((t) => (
        <div key={t.key} className={CARD} data-tally={t.key}>
          <span className={LABEL}>{t.label}</span>
          <span className="text-[12.5px] tabular-nums">{t.value}</span>
          {t.key === "exceptions" && <span className="text-[10.5px] text-ink-3">{scope}</span>}
        </div>
      ))}
    </div>
  );
}

function ExpensesGrid({
  view,
  budget,
  onRaise,
  onRequestSupport,
}: {
  view: ExpensesOut;
  budget: FiguresOut | undefined;
  onRaise: (() => void) | undefined;
  onRequestSupport: ((expenseId: string) => void) | undefined;
}): JSX.Element {
  const [cell, setCell] = useState<{ ref: string; citations: readonly string[] } | null>(null);
  const totalRow = view.rows.length + 2;
  const pick = (ref: string, citations: readonly string[]): void => {
    setCell({ ref, citations });
  };
  const amountCell = (
    row: ExpenseRowOut,
    letter: string,
    n: number,
    value: string | null | undefined,
  ) => {
    const ref = `${letter}${String(n)}`;
    return (
      <td
        key={ref}
        data-cell={ref}
        {...(cell?.ref === ref ? { "data-lit": "" } : {})}
        onClick={() => {
          pick(ref, row.citation_labels ?? []);
        }}
        className={cn(
          GRID,
          "cursor-pointer text-right tabular-nums",
          cell?.ref === ref && "bg-match",
        )}
      >
        {money(value)}
      </td>
    );
  };
  return (
    <section data-grid="expenses" className="mx-[12px] overflow-x-auto rounded-[12px] bg-card e1">
      <table className="w-full border-collapse">
        <thead>
          <tr aria-hidden className="h-[20px] bg-selected text-[11px] text-ink-3">
            <th className="w-[34px]" />
            {COPY.letters.map((l) => (
              <th key={l} className="font-normal">
                {l}
              </th>
            ))}
          </tr>
          <tr className="h-[26px] bg-faint">
            <th scope="row" className={NUM}>
              1
            </th>
            {COPY.columns.map((c) => (
              <th
                key={c}
                scope="col"
                className={cn(GRID, "h-[26px] text-left text-[11px] font-medium")}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {view.rows.map((row, i) => {
            const n = i + 2;
            return (
              <tr
                key={row.id}
                data-expense={row.line_key}
                data-exception={row.exception ? "" : undefined}
              >
                <th scope="row" className={NUM}>
                  <button
                    type="button"
                    aria-label={`${COPY.requestSupport} ${row.description}`}
                    onClick={() => onRequestSupport?.(row.id)}
                  >
                    {n}
                  </button>
                </th>
                <td className={GRID}>{row.description}</td>
                <td className={GRID}>{row.provider_name}</td>
                <td className={cn(GRID, row.exception && "bg-amber-tint")}>
                  {row.exception ? (
                    <span className="flex items-center justify-between gap-[8px]">
                      {COPY.noDisclosure(money(row.invoiced), row.description.toLowerCase())}
                      <Button
                        variant="secondary"
                        size="xs"
                        {...(onRaise === undefined ? {} : { onClick: onRaise })}
                      >
                        {COPY.raise}
                      </Button>
                    </span>
                  ) : (
                    row.disclosure_text
                  )}
                </td>
                {amountCell(row, "E", n, row.invoiced)}
                {amountCell(row, "F", n, row.credits)}
                {amountCell(row, "G", n, row.paid_from_plan)}
                <td className={cn(GRID, "text-center")}>{row.exception ? COPY.flag : "✓"}</td>
              </tr>
            );
          })}
          <tr data-row="total" className="font-medium">
            <th scope="row" className={NUM}>
              {totalRow}
            </th>
            <td className={GRID} colSpan={3}>
              {COPY.total}
            </td>
            <td className={cn(GRID, "text-right tabular-nums")}>{money(view.invoiced)}</td>
            <td className={cn(GRID, "text-right tabular-nums")}>{money(view.credits)}</td>
            <td className={cn(GRID, "text-right tabular-nums")}>{money(view.paid_from_plan)}</td>
            <td className={cn(GRID, "text-center")}>
              <Pill size="micro" variant={view.invoices_tie ? "green-tint" : "amber"}>
                {view.invoices_tie ? COPY.tally.tie : COPY.tally.off}
              </Pill>
            </td>
          </tr>
          <tr data-row="budget">
            <th scope="row" className={NUM}>
              {totalRow + 2}
            </th>
            <td className={GRID}>{COPY.budget}</td>
            <td className={GRID}>{COPY.budgetProvider}</td>
            <td className={GRID}>{COPY.budgetNote}</td>
            <td className={cn(GRID, "tabular-nums")} colSpan={3}>
              {(budget?.rows ?? []).map((r) => `${r.label} ${money(r.amount)}`).join(" · ")}
              {budget?.total !== undefined &&
                budget.total !== null &&
                ` · Dec 31 ${money(budget.total)}`}
            </td>
            <td className={cn(GRID, "text-center")}>✓</td>
          </tr>
          <tr data-row="plan">
            <th scope="row" className={NUM}>
              {totalRow + 3}
            </th>
            <td className={GRID}>{COPY.planDocument}</td>
            <td className={GRID}>{COPY.planCite}</td>
            <td className={GRID} colSpan={4}>
              {COPY.planNote}
            </td>
            <td className={cn(GRID, "text-center")} colSpan={2}>
              ✓
            </td>
          </tr>
        </tbody>
      </table>
      <p
        data-footer
        className="flex h-[30px] items-center px-[12px] text-[11.5px] text-ink-3 hairline-t"
      >
        {cell === null
          ? ""
          : COPY.footer(cell.ref, cell.citations.length, cell.citations.join(" · "))}
      </p>
    </section>
  );
}

function ComplianceGrid({
  tests,
  onReference,
}: {
  tests: readonly ComplianceTestOut[];
  onReference: ((screen: string) => void) | undefined;
}): JSX.Element {
  return (
    <section data-grid="compliance" className="mx-[12px] rounded-[12px] bg-card e1">
      <table className="w-full border-collapse">
        <thead>
          <tr className="h-[26px] bg-faint">
            {COPY.complianceColumns.map((c) => (
              <th
                key={c}
                scope="col"
                className={cn(GRID, "h-[26px] text-left text-[11px] font-medium")}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {tests.map((t) => {
            const words = COPY.tests[t.test_key];
            const screen = /^(EBP-\d\d)/.exec(words?.source ?? "")?.[1];
            return (
              <tr key={t.id} data-test-key={t.test_key}>
                <td className={GRID}>{words?.label ?? t.test_key}</td>
                <td className={GRID}>
                  {screen === undefined ? (
                    words?.source
                  ) : (
                    <button type="button" onClick={() => onReference?.(screen)}>
                      {words?.source}
                    </button>
                  )}
                </td>
                <td className={GRID}>{words?.limit}</td>
                <td className={GRID}>{words?.result}</td>
                <td className={GRID}>
                  {t.result === "exception" ? (
                    <Pill size="micro" variant="red-tint">
                      {COPY.exception}
                    </Pill>
                  ) : (
                    "✓"
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

function QualificationCard({ facts }: { facts: readonly QualificationFactOut[] }): JSX.Element {
  return (
    <section data-card="qualification" className="mx-[12px] rounded-[12px] bg-card e1">
      {facts.map((f) => (
        <div
          key={f.id}
          data-fact={f.fact_key}
          className="flex min-h-[34px] items-center gap-[12px] px-[14px] text-[12.5px] hairline-t"
        >
          <span className="w-[220px] text-ink-2">{COPY.facts[f.fact_key] ?? f.fact_key}</span>
          <span className="min-w-0 flex-1">{f.value}</span>
          {f.result === "consistent" && <span className="text-green">✓</span>}
        </div>
      ))}
    </section>
  );
}

export function useExpensesCanvas(
  workItemId: string,
  options: ExpensesOptions = {},
): CockpitCanvas {
  const on = useFlag(FLAG) === true;
  const enabled = options.active !== false && on;
  const path = { work_item_id: workItemId };
  const [localTab, setLocalTab] = useState<Tab>("expenses");
  const tab = options.tab ?? localTab;
  const expenses = useQuery({ ...ebpPlanExpensesOptions({ path }), enabled, retry: false });
  const budget = useQuery({ ...ebpBudgetAccountOptions({ path }), enabled, retry: false });
  const tests = useQuery({
    ...ebpComplianceTestsOptions({ path }),
    enabled: enabled && tab === "compliance",
    retry: false,
  });
  const facts = useQuery({
    ...ebpPlanQualificationOptions({ path }),
    enabled: enabled && tab === "qualification",
    retry: false,
  });
  const view = expenses.data;
  const source = options.onSourceDocs === undefined ? {} : { onClick: options.onSourceDocs };
  const signOff = options.onSignOff === undefined ? {} : { onClick: options.onSignOff };
  const signed = options.signedInitials != null;
  const testRows = tests.data ?? [];
  const factRows = facts.data ?? [];
  return {
    title: COPY.title,
    actions: (
      <>
        {signed ? (
          <Pill size="chip" variant="green-tint" check>
            {options.signedInitials}
          </Pill>
        ) : (
          <Pill size="micro" variant="neutral">
            {COPY.agentDraft}
          </Pill>
        )}
        <PaneAction label={COPY.edit} />
        <PaneAction label={COPY.signOff} {...signOff} />
        <PaneAction label={COPY.sourceDocs} {...source} />
      </>
    ),
    controls: (
      <div className="flex w-full items-center justify-between">
        <Segmented
          label={COPY.title}
          active={COPY.tabs[tab]}
          onChange={(label) => {
            const next = TABS.find((value) => COPY.tabs[value] === label);
            if (next !== undefined) {
              setLocalTab(next);
              options.onTab?.(next);
            }
          }}
          options={TABS.map((value) => COPY.tabs[value])}
        />
        <PaneAction label={COPY.openInExcel} />
      </div>
    ),
    children:
      view === undefined ? (
        <Skeleton className="m-[12px] h-[240px]" />
      ) : (
        <div
          data-screen="EBP-09"
          data-tab={tab}
          className="flex min-h-0 flex-1 flex-col gap-[12px] overflow-y-auto bg-shell pb-[12px]"
        >
          {tab === "expenses" && (
            <>
              <Tally
                scope={COPY.tally.scopeExpenses}
                items={[
                  { key: "paid", label: COPY.tally.paid, value: money(view.paid_from_plan) },
                  {
                    key: "disclosure",
                    label: COPY.tally.disclosure,
                    value: view.exceptions === 0 ? COPY.tally.tie : COPY.tally.off,
                  },
                  { key: "budget", label: COPY.tally.budget, value: money(budget.data?.total) },
                  {
                    key: "scheduleH",
                    label: COPY.tally.scheduleH,
                    value: view.invoices_tie ? COPY.tally.tie : COPY.tally.off,
                  },
                  {
                    key: "exceptions",
                    label: COPY.tally.exceptions,
                    value: String(view.exceptions),
                  },
                ]}
              />
              <ExpensesGrid
                view={view}
                budget={budget.data}
                onRaise={options.onRaise}
                onRequestSupport={options.onRequestSupport}
              />
            </>
          )}
          {tab === "compliance" && (
            <>
              <Tally
                scope={COPY.tally.scopeCompliance}
                items={[
                  { key: "tests", label: COPY.tally.tests, value: String(testRows.length) },
                  {
                    key: "exceptions",
                    label: COPY.tally.exceptions,
                    value: String(testRows.filter((t) => t.result === "exception").length),
                  },
                ]}
              />
              <ComplianceGrid tests={testRows} onReference={options.onReference} />
            </>
          )}
          {tab === "qualification" && (
            <>
              <Tally
                scope={COPY.tally.scopeQualification}
                items={[
                  {
                    key: "consistent",
                    label: COPY.tally.consistent,
                    value: String(factRows.filter((f) => f.result === "consistent").length),
                  },
                  {
                    key: "exceptions",
                    label: COPY.tally.exceptions,
                    value: String(factRows.filter((f) => f.result === "exception").length),
                  },
                ]}
              />
              <QualificationCard facts={factRows} />
            </>
          )}
        </div>
      ),
  };
}
