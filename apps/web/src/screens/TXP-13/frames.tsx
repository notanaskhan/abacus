// TXP-13 frames a–c3 (T-06-T52; TASK-9031; DEC-6036): the other-entity workpapers in the statement
// grammar, one frame per form. a is the 1120-S's Schedule M-2 and shareholder allocation, b and
// b2 the 1120's ASC 740 provision with its rate reconciliation and deferred inventory, c and c2
// the 990's Part IX and its allocation basis, c3 Part IX while the time-study allocation runs.
// Every figure is the server's (T-06-T42's reads with T-06-T52's lines); the browser formats and
// compares two server figures for a tie pill, and never adds. The DF-08 views (Shareholder
// allocation, Rate reconciliation, Deferred inventory, Allocation basis) are the control bar's
// segments. No partnership words appear here. A Filed or Accepted return reads with its values
// in ink-2 and a lock.
import type {
  TaxDepthAaaOut,
  TaxDepthFunctionalExpensesOut,
  TaxDepthProvisionOut,
  TaxReturnRowOut,
} from "@abacus/api-client";
import {
  aaaOptions,
  functionalExpensesOptions,
  provisionExplainMutation,
  provisionOptions,
} from "@abacus/api-client/query";
import {
  Button,
  Icon,
  RegistryStatus,
  Segmented,
  SkeletonRows,
  TallyStrip,
  type TallyItem,
  amount,
  cn,
  date,
  ratio,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenOverlay } from "../../app-core/open";
import { ov } from "../../routes/to";
import { FRAMES as F } from "./copy";

const money = (v: string | number | null | undefined): string =>
  v === null || v === undefined ? "—" : amount(String(v), "whole").text;
// The reads carry percents (28.5), not ratios: one place, as the statement shows them.
const pct = (v: string | number | null | undefined): string =>
  v === null || v === undefined ? "—" : `${ratio(String(v), 1)}%`;
const same = (a: string | number | null | undefined, b: string | number | null | undefined) =>
  a !== null && a !== undefined && b !== null && b !== undefined && Number(a) === Number(b);

function Head({
  row,
  tabs,
  active,
  views,
  view,
  onView,
  center,
}: {
  row: TaxReturnRowOut;
  tabs: readonly string[];
  active: string;
  views: readonly string[];
  view: string;
  onView: (v: string) => void;
  center: string;
}): JSX.Element {
  const now = useNow();
  const locked = row.status === "filed" || row.status === "accepted";
  return (
    <>
      <div className="flex h-[46px] flex-none items-center justify-center gap-[8px] px-[12px]">
        <span className="text-[15px] font-medium" data-txp13="title">
          {F.title(row.tax_year, row.form)}
        </span>
        {row.fiscal_year_end ? (
          <span className="text-[13px] text-ink-3" data-txp13="fye">
            {F.fye(date(row.fiscal_year_end, { now, withYear: true, tz: "UTC" }))}
          </span>
        ) : null}
        <span className="text-[13px] text-ink-2">{row.client_name}</span>
        <RegistryStatus object="return" code={row.status} />
        {locked ? <Icon name="lock" size={12} className="text-ink-3" label={F.locked} /> : null}
      </div>
      <div className="flex h-[44px] flex-none items-center px-[12px]">
        <Segmented size="small" label={F.tabsLabel} options={tabs} active={active} />
      </div>
      <div className="relative flex h-[44px] flex-none items-center px-[12px]">
        <Segmented
          size="small"
          label={F.viewsLabel}
          options={views}
          active={view}
          onChange={onView}
        />
        <span className="absolute inset-x-0 text-center text-[13px] font-medium pointer-events-none">
          {center}
        </span>
      </div>
    </>
  );
}

function Pane({
  title,
  children,
  className,
}: {
  title: string;
  children: ReactNode;
  className?: string;
}): JSX.Element {
  return (
    <section
      aria-label={title}
      className={cn("min-w-0 overflow-hidden rounded-[12px] bg-card shadow-e1", className)}
    >
      <h2 className="flex h-[40px] items-center px-[14px] text-[14px] font-medium">{title}</h2>
      {children}
    </section>
  );
}

type Cell = { text: string; total?: boolean };

function Table({
  head,
  rows,
  muted,
  label,
}: {
  head: readonly string[];
  rows: readonly (readonly (string | Cell)[])[];
  muted: boolean;
  label: string;
}): JSX.Element {
  return (
    <table aria-label={label} className="w-full border-collapse text-[13px]">
      <thead>
        <tr className="hairline-b">
          {head.map((h, i) => (
            <th
              key={h}
              scope="col"
              className={cn(
                "h-[32px] px-[10px] text-[12px] font-normal text-ink-3",
                i < 2 ? "text-left" : "text-right",
              )}
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r, ri) => {
          const total = r.some((c) => typeof c !== "string" && c.total === true);
          return (
            <tr
              key={ri}
              className={cn(
                "hairline-b",
                total && "font-medium shadow-[inset_0_-3px_0_-1px_var(--color-ink)]",
              )}
            >
              {r.map((c, i) => {
                const text = typeof c === "string" ? c : c.text;
                return (
                  <td
                    key={i}
                    className={cn(
                      "h-[34px] px-[10px]",
                      i < 2 ? "text-left" : "text-right tabular-nums",
                      text === "—" ? "text-ink-4" : muted ? "text-ink-2" : "",
                      text.startsWith("(") && "text-red-ink",
                    )}
                  >
                    {text}
                  </td>
                );
              })}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function tally(label: string, tie: boolean, off?: string): TallyItem {
  return tie ? { label, tally: "tie" } : { label, tally: "off", vars: { amount: off ?? "" } };
}

// ---- Frame A · 1120-S ---------------------------------------------------------------------------

const REDUCTIONS: ReadonlySet<number> = new Set([4, 5, 7]);

export function AaaFrame({
  returnId,
  row,
}: {
  returnId: string;
  row: TaxReturnRowOut;
}): JSX.Element {
  const [view, setView] = useState<string>(F.a.views[0]);
  const q = useQuery(aaaOptions({ path: { return_id: returnId } }));
  const data: TaxDepthAaaOut | undefined = q.data;
  const muted = data?.locked ?? false;
  const line = (n: number) => data?.lines?.find((l) => l.line_no === n)?.aaa;
  return (
    <div data-screen="TXP-13" data-frame="a" className="flex min-h-0 flex-1 flex-col">
      <Head
        row={row}
        tabs={F.a.tabs}
        active={F.a.active}
        views={F.a.views}
        view={view}
        onView={setView}
        center={F.a.center}
      />
      {data === undefined ? (
        <SkeletonRows type="table" label={F.loading} />
      ) : (
        <>
          <TallyStrip
            label={F.tally}
            className="flex-none px-[12px] py-[10px]"
            items={[
              tally(F.a.foots, same(line(8), data.aaa)),
              { label: F.a.begin, value: money(line(1)), info: F.a.beginInfo },
              { label: F.a.income, value: money(line(2)), info: F.a.incomeInfo },
              { label: F.a.distributions, value: money(line(7)), info: F.a.distributionsInfo },
              { label: F.a.end, value: money(data.aaa), info: F.a.endInfo },
              tally(F.a.within, Number(line(7) ?? 0) <= Number(line(6) ?? 0)),
            ]}
          />
          <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
            {view === F.a.views[0] ? (
              <Pane title={F.a.m2} className="flex-1">
                <Table
                  label={F.a.m2}
                  muted={muted}
                  head={F.a.m2Head}
                  rows={(data.lines ?? []).map((l) => {
                    // Lines 4, 5 and 7 reduce the account: the form prints them in parentheses.
                    const shown = (v: string) =>
                      REDUCTIONS.has(l.line_no) && Number(v) !== 0 ? money(`-${v}`) : money(v);
                    return [
                      String(l.line_no),
                      F.a.m2Lines[l.line_no] ?? "",
                      { text: shown(l.aaa), total: l.line_no === 8 },
                      shown(l.pti),
                      shown(l.e_and_p),
                      shown(l.oaa),
                    ];
                  })}
                />
              </Pane>
            ) : null}
            <Pane title={F.a.allocation} className="flex-1">
              <Table
                label={F.a.allocation}
                muted={muted}
                head={F.a.allocationHead}
                rows={[
                  ...(data.shareholders ?? []).map((h) => [
                    h.name,
                    "",
                    pct(h.pct),
                    money(h.ordinary_income),
                    money(h.interest),
                    money(h.nondeductible),
                    money(h.distributions),
                  ]),
                ]}
              />
              <p className="px-[14px] py-[10px] text-[11.5px] text-ink-3">{F.a.note}</p>
            </Pane>
          </div>
        </>
      )}
    </div>
  );
}

// ---- Frame B · 1120 + ASC 740 -------------------------------------------------------------------

export function ProvisionFrame({
  returnId,
  row,
  fallback,
}: {
  returnId: string;
  row: TaxReturnRowOut;
  /** What a return with no provision yet shows instead. */
  fallback?: ReactNode;
}): JSX.Element {
  const openOverlay = useOpenOverlay();
  const [view, setView] = useState<string>(F.b.views[0]);
  const q = useQuery(provisionOptions({ path: { return_id: returnId } }));
  const explain = useMutation({
    ...provisionExplainMutation(),
    onSuccess: (out) => {
      if (out.issue_id) openOverlay(ov.SHL15(out.issue_id));
    },
    onError: () => {
      toast.show({ kind: "error", text: F.b.explainFailed });
    },
  });
  const data: TaxDepthProvisionOut | undefined = q.data;
  const locked = row.status === "filed" || row.status === "accepted";
  if (q.isError && fallback !== undefined) return <>{fallback}</>;
  const unclassified = (data?.recon_items ?? []).filter(
    (r) => r.classification === "unclassified",
  );
  const recon = (data?.recon_items ?? []).filter((r) => r.classification !== "unclassified");
  return (
    <div data-screen="TXP-13" data-frame="b" className="flex min-h-0 flex-1 flex-col">
      <Head
        row={row}
        tabs={F.b.tabs}
        active={F.b.active}
        views={F.b.views}
        view={view}
        onView={setView}
        center={F.b.center(row.tax_year)}
      />
      {data === undefined ? (
        <SkeletonRows type="table" label={F.loading} />
      ) : (
        <>
          <TallyStrip
            label={F.tally}
            className="flex-none px-[12px] py-[10px]"
            items={[
              { label: F.b.pretax, value: money(data.pretax_book_income), info: F.b.pretaxInfo },
              { label: F.b.taxable, value: money(data.taxable_income), info: F.b.taxableInfo },
              { label: F.b.blended, value: pct(data.blended_rate), info: F.b.blendedInfo },
              { label: F.b.total, value: money(data.total), info: F.b.totalInfo },
              { label: F.b.etr, value: pct(data.effective_rate), info: F.b.etrInfo },
              tally(F.b.recon, data.rate_reconciliation_tally === "tie", money(data.unclassified)),
            ]}
          />
          <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
            {view === F.b.views[0] ? (
              <Pane title={F.b.current} className="flex-1">
                <Table
                  label={F.b.current}
                  muted={locked}
                  head={F.b.currentHead}
                  rows={[
                    [F.b.lines.pretax, "", money(data.pretax_book_income)],
                    [F.b.lines.permanent, "", money(data.permanent_total)],
                    ...(data.deferred_items ?? []).map((d) => [
                      d.label,
                      "",
                      money(
                        d.kind === "dtl" ? `-${d.temporary_difference}` : d.temporary_difference,
                      ),
                    ]),
                    [F.b.lines.taxable, "", { text: money(data.taxable_income), total: true }],
                    [F.b.lines.current(pct(data.blended_rate)), "", money(data.current)],
                    [F.b.lines.deferred(pct(data.blended_rate)), "", money(data.deferred)],
                    [F.b.lines.total, "", { text: money(data.total), total: true }],
                  ]}
                />
              </Pane>
            ) : null}
            {view !== F.b.views[2] ? (
              <Pane title={F.b.views[1]} className="flex-1">
                <Table
                  label={F.b.views[1]}
                  muted={locked}
                  head={F.b.reconHead}
                  rows={[
                    ...recon.map((r) => [r.description, "", pct(r.rate_effect), money(r.amount)]),
                    [
                      F.b.lines.reconTotal,
                      "",
                      { text: pct(data.effective_rate), total: true },
                      money(data.total),
                    ],
                  ]}
                />
                {unclassified.map((u) => (
                  <div
                    key={u.item_id}
                    data-txp13="unclassified"
                    className="flex min-h-[40px] items-center gap-[10px] bg-amber-tint px-[14px] py-[6px] text-[13px]"
                  >
                    <span className="min-w-0 flex-1">{F.b.unclassified(money(u.amount))}</span>
                    <Button
                      variant="tonal"
                      size="sm"
                      disabled={locked || explain.isPending}
                      onClick={() => {
                        explain.mutate({ path: { return_id: returnId, item_id: u.item_id } });
                      }}
                    >
                      {F.b.explain}
                    </Button>
                  </div>
                ))}
              </Pane>
            ) : null}
            {view === F.b.views[2] ? (
              <Pane title={F.b.views[2]} className="flex-1">
                <Table
                  label={F.b.views[2]}
                  muted={locked}
                  head={F.b.deferredHead}
                  rows={[
                    ...(data.deferred_items ?? []).map((d) => [
                      `${d.kind === "dtl" ? F.b.dtl : F.b.dta} ${d.label}`,
                      "",
                      money(d.temporary_difference),
                      pct(d.rate),
                      money(d.amount),
                    ]),
                    [
                      F.b.lines.netDeferred,
                      "",
                      "",
                      "",
                      { text: money(data.deferred), total: true },
                    ],
                  ]}
                />
              </Pane>
            ) : null}
          </div>
        </>
      )}
    </div>
  );
}

// ---- Frame C · 990 ------------------------------------------------------------------------------

export function PartIxFrame({
  returnId,
  row,
}: {
  returnId: string;
  row: TaxReturnRowOut;
}): JSX.Element {
  const [view, setView] = useState<string>(F.c.views[0]);
  const q = useQuery(functionalExpensesOptions({ path: { return_id: returnId } }));
  const data: TaxDepthFunctionalExpensesOut | undefined = q.data;
  const locked = row.status === "filed" || row.status === "accepted";
  return (
    <div data-screen="TXP-13" data-frame="c" className="flex min-h-0 flex-1 flex-col">
      <Head
        row={row}
        tabs={F.c.tabs}
        active={F.c.active}
        views={F.c.views}
        view={view}
        onView={setView}
        center={F.c.center}
      />
      {data === undefined ? (
        <div className="flex flex-col gap-[8px] p-[12px]" data-txp13="building">
          <p className="text-[12.5px] text-ink-3">{F.c.building}</p>
          <SkeletonRows type="table" label={F.c.building} />
        </div>
      ) : (
        <>
          <TallyStrip
            label={F.tally}
            className="flex-none px-[12px] py-[10px]"
            items={[
              {
                label: F.c.ties,
                pill: { text: money(data.total), variant: "green", check: true },
              },
              { label: F.c.program, value: money(data.program), info: F.c.programInfo },
              { label: F.c.management, value: money(data.management), info: F.c.managementInfo },
              {
                label: F.c.fundraising,
                value: money(data.fundraising),
                info: F.c.fundraisingInfo,
              },
              { label: F.c.ratio, value: pct(data.program_ratio), info: F.c.ratioInfo },
              { label: F.c.support, value: pct(data.public_support), info: F.c.supportInfo },
            ]}
          />
          <div className="flex min-h-0 flex-1 px-[12px] pb-[12px]">
            <Pane title={view === F.c.views[0] ? F.c.center : F.c.views[1]} className="flex-1">
              {view === F.c.views[0] ? (
                <Table
                  label={F.c.center}
                  muted={locked}
                  head={F.c.head}
                  rows={[
                    ...(data.lines ?? []).map((l) => [
                      l.line,
                      l.label,
                      money(l.total),
                      money(l.program),
                      money(l.management),
                      money(l.fundraising),
                    ]),
                    [
                      "25",
                      F.c.totalLine,
                      { text: money(data.total), total: true },
                      money(data.program),
                      money(data.management),
                      money(data.fundraising),
                    ],
                  ]}
                />
              ) : (
                <Table
                  label={F.c.views[1]}
                  muted={locked}
                  head={F.c.basisHead}
                  rows={(data.lines ?? []).map((l) => [
                    l.line,
                    l.label,
                    F.c.basis[l.basis] ?? l.basis,
                    l.time_study ? pct(l.time_study["program"]) : "—",
                    l.time_study ? pct(l.time_study["management_general"]) : "—",
                    l.time_study ? pct(l.time_study["fundraising"]) : "—",
                  ])}
                />
              )}
            </Pane>
          </div>
        </>
      )}
    </div>
  );
}
