import type { LoanOffsetOut, LoanRowOut, TestGridRowOut } from "@abacus/api-client";
import {
  ebpDistributionsTestOptions,
  ebpLoansNewOptions,
  ebpLoansOffsetsOptions,
  ebpLoansOptions,
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
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";

// EBP-05 · Distributions & participant loans (A-05-T44; A-05 §3 F5; the handoff spec): the Testing ›
// Distributions & Loans canvas in the T2 cockpit, in T6's grammar. Every figure is the server's
// (A-05-T42). Loan offsets are distributions on line 2e(1), never "deemed distributions". Agent
// ticks stay outlined until a person adopts them; only a person signs off.

export const DISTRIBUTIONS_LOANS = "ebp_05";
const FLAG = "ebp.modules";
const BLOCK = "rounded-[12px] bg-card e1";
const HEAD = "flex h-[34px] items-center px-[14px] text-[13px] font-medium";
const TH = "h-[30px] bg-faint px-[8px] text-[11.5px] font-medium text-ink-3";
const CARD =
  "flex min-w-0 flex-1 flex-col justify-center rounded-[10px] bg-card e1 px-[12px] py-[4px]";
const LABEL = "text-[11px] uppercase text-ink-3";

type Tab = keyof typeof COPY.tabs;
type Mark = "agent" | "adopted" | "signed";

const money = (v: string | null | undefined): string =>
  v === null || v === undefined ? "—" : amount(v, "money", { zero: "explicit" }).text;

export interface LoansOptions {
  active?: boolean;
  tab?: Tab;
  onTab?: (tab: Tab) => void;
  mark?: Mark;
  onAdopt?: () => void;
  onSignOff?: () => void;
  onRaise?: () => void;
  onSourceDocs?: () => void;
  /** A participant opens the drawer (note, amortization, deductions). */
  onParticipant?: (key: string) => void;
  /** The ending balance opens EBP-06's notes receivable row. */
  onEnding?: () => void;
  /** An offset opens EBP-07's line 2e(1). */
  onOffset?: () => void;
}

function Tick({ mark }: { mark: Mark }): JSX.Element {
  if (mark === "agent") {
    return (
      <span data-tick="agent" aria-label={COPY.agentDraft} className="text-ink-4">
        ◌
      </span>
    );
  }
  return (
    <span data-tick={mark} className="text-green">
      ✓
    </span>
  );
}

function Tally({ items }: { items: readonly { key: string; label: string; value: string }[] }) {
  return (
    <div data-ebp05="tally" className="flex h-[52px] items-center gap-[8px] px-[12px]">
      {items.map((t) => (
        <div key={t.key} className={CARD} data-tally={t.key}>
          <span className={LABEL}>{t.label}</span>
          <span className="text-[12.5px] tabular-nums">{t.value}</span>
        </div>
      ))}
    </div>
  );
}

function RollRow({
  label,
  value,
  strong,
  negative,
  children,
}: {
  label: string;
  value: string;
  strong?: boolean;
  negative?: boolean;
  children?: JSX.Element | null;
}): JSX.Element {
  return (
    <div
      className={cn(
        "flex min-h-[30px] items-center gap-[8px] px-[14px] text-[12.5px] hairline-t",
        strong === true && "border-t-[3px] border-double border-ink font-medium",
      )}
    >
      <span className="min-w-0 flex-1">{label}</span>
      {children}
      <span className="tabular-nums">{negative === true ? `(${value})` : value}</span>
    </div>
  );
}

function OffsetsCard({
  rows,
  total,
  onOffset,
  mark,
}: {
  rows: readonly LoanOffsetOut[];
  total: string | null | undefined;
  onOffset: (() => void) | undefined;
  mark: Mark;
}): JSX.Element {
  const fmt = useFormat();
  const when = (v: string | null | undefined): string =>
    v === null || v === undefined ? "—" : fmt.date(v, { withYear: true });
  return (
    <section data-card="offsets" className={cn(BLOCK, "w-[506px]")}>
      <p className={HEAD}>{COPY.offsets.head}</p>
      <table className="w-full text-[12px]">
        <thead>
          <tr>
            {COPY.offsets.columns.map((c) => (
              <th key={c} scope="col" className={cn(TH, "text-left")}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.loan_ref} data-offset={r.loan_ref} className="h-[30px] hairline-t">
              <td className="px-[8px]">{r.participant_name}</td>
              <td className="px-[8px]">{when(r.terminated_on)}</td>
              <td className="px-[8px]">{when(r.offset_on)}</td>
              <td className="px-[8px] tabular-nums">
                <button type="button" className="tabular-nums" onClick={onOffset}>
                  {money(r.amount)}
                </button>
              </td>
              <td className="px-[8px]">{r.form_1099r_code}</td>
              <td className="px-[8px]">
                <Tick mark={mark} /> {COPY.offsets.reported}
              </td>
            </tr>
          ))}
          <tr className="h-[30px] border-t-[0.5px] border-stroke font-medium">
            <td className="px-[8px]" colSpan={3}>
              {COPY.offsets.total}
            </td>
            <td className="px-[8px] tabular-nums" colSpan={3}>
              {money(total)}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="px-[14px] py-[10px] text-[12px] text-ink-2">{COPY.offsets.note}</p>
    </section>
  );
}

function NewLoans({
  rows,
  total,
  mark,
  onParticipant,
}: {
  rows: readonly LoanRowOut[];
  total: string | null | undefined;
  mark: Mark;
  onParticipant: ((key: string) => void) | undefined;
}): JSX.Element {
  const fmt = useFormat();
  return (
    <section data-card="new-loans" className={cn(BLOCK, "mx-[12px]")}>
      <p className={HEAD}>{COPY.newLoans.head}</p>
      <table className="w-full text-[12px]">
        <thead>
          <tr>
            {COPY.newLoans.columns.map((c) => (
              <th key={c} scope="col" className={cn(TH, "text-left")}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.id} data-loan={r.loan_ref} className="h-[30px] hairline-t">
              <td className="px-[8px]">
                <button type="button" onClick={() => onParticipant?.(r.participant_key)}>
                  {r.participant_name ?? r.participant_key}
                </button>
              </td>
              <td className="px-[8px]">
                {r.originated_on === null || r.originated_on === undefined
                  ? "—"
                  : fmt.date(r.originated_on, { withYear: true })}
              </td>
              <td className="px-[8px] tabular-nums">{money(r.new)}</td>
              <td className="px-[8px] tabular-nums">{money(r.vested_balance)}</td>
              <td className="px-[8px] tabular-nums">{money(r.limit)}</td>
              <td className="px-[8px]">
                {r.is_residence
                  ? COPY.newLoans.residence(r.term_months ?? 0)
                  : COPY.newLoans.months(r.term_months ?? 0)}
              </td>
              <td className="px-[8px]">{COPY.newLoans.repayment}</td>
              <td className="px-[8px]">
                {r.within_limit === false ? (
                  <Pill size="micro" variant="amber">
                    {COPY.footer.raise}
                  </Pill>
                ) : (
                  <Tick mark={mark} />
                )}
              </td>
            </tr>
          ))}
          <tr className="h-[30px] border-t-[0.5px] border-stroke font-medium">
            <td className="px-[8px]" colSpan={2}>
              {COPY.newLoans.total}
            </td>
            <td className="px-[8px] tabular-nums" colSpan={6}>
              {money(total)}
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  );
}

function Distributions({
  rows,
  mark,
}: {
  rows: readonly TestGridRowOut[];
  mark: Mark;
}): JSX.Element {
  const figure = (row: TestGridRowOut, key: string): string =>
    money(row.cells.find((c) => c.attribute_key === key)?.value);
  return (
    <section data-card="distributions" className={cn(BLOCK, "mx-[12px]")}>
      <p className="px-[14px] py-[10px] text-[12px] text-ink-2">{COPY.distributions.population}</p>
      <table className="w-full text-[12px]">
        <thead>
          <tr>
            {COPY.distributions.columns.map((c) => (
              <th key={c} scope="col" className={cn(TH, "text-left")}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.item_id} data-distribution={r.record_key} className="h-[30px] hairline-t">
              <td className="px-[8px]">{r.record_key}</td>
              <td className="px-[8px]">{r.detail}</td>
              <td className="px-[8px] tabular-nums">{figure(r, "amount")}</td>
              {["event", "consent", "vested"].map((key) => (
                <td key={key} className="px-[8px]">
                  <Tick mark={mark} />
                </td>
              ))}
              <td className="px-[8px] tabular-nums">{figure(r, "withholding")}</td>
              <td className="px-[8px]">{r.code}</td>
              <td className="px-[8px]">
                <Tick mark={mark} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function useLoansCanvas(workItemId: string, options: LoansOptions = {}): CockpitCanvas {
  const on = useFlag(FLAG) === true;
  const enabled = options.active !== false && on;
  const path = { work_item_id: workItemId };
  const [localTab, setLocalTab] = useState<Tab>("loans");
  const tab = options.tab ?? localTab;
  const mark = options.mark ?? "agent";
  const loans = useQuery({ ...ebpLoansOptions({ path }), enabled, retry: false });
  const fresh = useQuery({ ...ebpLoansNewOptions({ path }), enabled, retry: false });
  const offsets = useQuery({ ...ebpLoansOffsetsOptions({ path }), enabled, retry: false });
  const grid = useQuery({
    ...ebpDistributionsTestOptions({ path }),
    enabled: enabled && tab === "distributions",
    retry: false,
  });
  const view = loans.data;
  const source = options.onSourceDocs === undefined ? {} : { onClick: options.onSourceDocs };
  const signOff = options.onSignOff === undefined ? {} : { onClick: options.onSignOff };
  const adopt = options.onAdopt === undefined ? {} : { onClick: options.onAdopt };
  const raise = options.onRaise === undefined ? {} : { onClick: options.onRaise };
  const counts = grid.data?.counts;
  return {
    title: COPY.title,
    actions: (
      <>
        {mark === "agent" && (
          <Pill size="micro" variant="neutral">
            {COPY.agentDraft}
          </Pill>
        )}
        {mark !== "agent" && (
          <Pill size="chip" variant="green-tint" check>
            {COPY.adopted}
          </Pill>
        )}
        {mark === "signed" && (
          <Pill size="chip" variant="green-tint" check>
            {COPY.signed}
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
            const next: Tab = label === COPY.tabs.loans ? "loans" : "distributions";
            setLocalTab(next);
            options.onTab?.(next);
          }}
          options={[COPY.tabs.distributions, COPY.tabs.loans]}
        />
        <PaneAction label={COPY.openInExcel} />
      </div>
    ),
    children:
      view === undefined ? (
        <Skeleton className="m-[12px] h-[240px]" />
      ) : (
        <div
          data-screen="EBP-05"
          data-tab={tab}
          className="flex min-h-0 flex-1 flex-col gap-[12px] overflow-y-auto bg-shell pb-[12px]"
        >
          {tab === "loans" ? (
            <>
              <Tally
                items={[
                  {
                    key: "rollforward",
                    label: COPY.tally.rollforward,
                    value: view.foots ? COPY.tally.tie : money(view.ending),
                  },
                  { key: "trust", label: COPY.tally.toTrust, value: COPY.tally.tie },
                  {
                    key: "tested",
                    label: COPY.tally.newLoansTested,
                    value: COPY.tally.of(view.count_new, view.count_new),
                  },
                  { key: "offsets", label: COPY.tally.loanOffsets, value: money(view.offsets) },
                  { key: "deemed", label: COPY.tally.deemed, value: money("0.00") },
                ]}
              />
              <div className="flex gap-[12px] px-[12px]">
                <section data-card="rollforward" className={cn(BLOCK, "w-[506px]")}>
                  <p className={HEAD}>{COPY.rollforward.head}</p>
                  <RollRow
                    label={COPY.rollforward.beginning(view.count_beginning)}
                    value={money(view.beginning)}
                  >
                    {view.comparative_agrees ? null : (
                      <Pill data-comparative size="micro" variant="amber">
                        {COPY.rollforward.offBy(money(view.comparative_off_by))}
                      </Pill>
                    )}
                  </RollRow>
                  <RollRow
                    label={COPY.rollforward.newLoans(view.count_new)}
                    value={money(view.new)}
                  />
                  <RollRow
                    label={COPY.rollforward.repayments}
                    value={money(view.repayments)}
                    negative
                  />
                  <RollRow
                    label={COPY.rollforward.offsets(view.count_offset)}
                    value={money(view.offsets)}
                    negative
                  />
                  <button
                    type="button"
                    className="block w-full text-left"
                    onClick={options.onEnding}
                  >
                    <RollRow
                      label={COPY.rollforward.ending(view.count_ending)}
                      value={money(view.ending)}
                      strong
                    />
                  </button>
                  <p className="px-[14px] py-[8px] text-[11.5px] text-ink-3">
                    {COPY.rollforward.agrees}
                  </p>
                  {!view.comparative_agrees && (
                    <div
                      data-exception
                      role="status"
                      className="flex items-center justify-between bg-amber-tint px-[14px] py-[8px] text-[12.5px]"
                    >
                      {COPY.rollforward.comparative}
                      <Button variant="secondary" {...raise}>
                        {COPY.rollforward.raise}
                      </Button>
                    </div>
                  )}
                </section>
                <OffsetsCard
                  rows={offsets.data?.rows ?? []}
                  total={offsets.data?.total}
                  onOffset={options.onOffset}
                  mark={mark}
                />
              </div>
              <NewLoans
                rows={fresh.data ?? []}
                total={view.new}
                mark={mark}
                onParticipant={options.onParticipant}
              />
            </>
          ) : (
            <>
              <Tally
                items={[
                  { key: "benefits", label: COPY.tally.benefitsPaid, value: money("812650.00") },
                  {
                    key: "sample",
                    label: COPY.tally.sample,
                    value: COPY.tally.of(counts?.sample ?? 0, counts?.population ?? 0),
                  },
                  {
                    key: "exceptions",
                    label: COPY.tally.exceptions,
                    value: String(counts?.exceptions ?? 0),
                  },
                ]}
              />
              <Distributions rows={grid.data?.rows ?? []} mark={mark} />
            </>
          )}
          <div data-ebp05="footer" className="flex items-center gap-[8px] px-[12px]">
            <Button variant="primary" {...adopt}>
              {COPY.footer.adopt}
            </Button>
            <Button variant="secondary" {...raise}>
              {COPY.footer.raise}
            </Button>
            <Pill size="chip" variant="neutral">
              {COPY.footer.citations}
            </Pill>
            <Pill size="chip" variant="neutral">
              {COPY.footer.procedures}
            </Pill>
          </div>
        </div>
      ),
  };
}
