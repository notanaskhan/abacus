import type { FiguresOut, LateRemittanceOut, PayrollOut } from "@abacus/api-client";
import {
  ebpContributionsOptions,
  ebpLateRemittancesOptions,
  ebpPayrollsOptions,
  ebpSchedule4aOptions,
} from "@abacus/api-client/query";
import {
  Amount,
  Button,
  type CockpitCanvas,
  Icon,
  PaneAction,
  Pill,
  Segmented,
  Skeleton,
  type ViewState,
  amount,
  cn,
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useFlag } from "../../app-core/flags";
import { COPY } from "./copy";
import { ContributionsTesting } from "./Testing";

// EBP-04 · Contributions & remittance timeliness (A-05-T31; A-05 §3 F6, SPEC-640; the handoff
// spec): the Testing › Contributions & Remittance canvas in the T2 cockpit, T6 grammar. The tally
// strip, Card A (the server's reconciliation rows in ledger grammar, "$" cents), Card B (the
// 26-dot payroll timeline and the payroll table from `…/ebp/contributions/payrolls`), Card C (the
// single late remittance with both day counts, lost earnings, the correction status and Form 5330
// exactly as recorded, and the Schedule H line 4a preview) and Raise exception… / Draft 4a schedule.
// "Corrected" is never inferred from the clock: it is the late remittance's recorded status (f). The
// browser does no arithmetic (ADR-050). The Testing tab (c) is `Testing.tsx` (A-05-T32).

export type ContributionsTab = "reconciliation" | "timeliness" | "testing";
const TABS: readonly ContributionsTab[] = ["reconciliation", "timeliness", "testing"];

const CARD =
  "flex h-[40px] flex-1 flex-col justify-center rounded-[10px] bg-card px-[12px] shadow-e1";
const LABEL = "text-micro font-medium uppercase tracking-[.07em] text-ink-3";
const BLOCK = "flex flex-col rounded-pane bg-card shadow-e1";
const BLOCK_HEAD = "flex h-[40px] items-center px-[14px] text-[13.5px] font-medium hairline-b";

const money = (v: string | null | undefined): string => amount(v ?? "", "money").text;

export interface ContributionsOptions {
  active: boolean;
  /** The run is executing this section (d): tallies read Pending, Card A is a skeleton. */
  running?: boolean;
  tab?: ContributionsTab;
  onTab?: (tab: ContributionsTab) => void;
  /** SHL-15 over the late remittance (and the cutoff receivable). */
  onRaise?: () => void;
  /** EBP-07 Supplemental schedules. */
  onDraft4a?: () => void;
  /** The Dec 26 deposit drawer (`?ov=payroll:<id>`). */
  onPayroll?: (payrollId: string) => void;
  /** A-05-T32: EBP-03 on a participant's sample item. */
  onEligibility?: (itemId: string) => void;
}

function Tally({
  late,
  receivable,
  ties,
  running,
}: {
  late: readonly LateRemittanceOut[];
  receivable: string | null;
  ties: readonly { key: string; label: string }[];
  running: boolean;
}): JSX.Element {
  const first = late[0];
  return (
    <div data-ebp04="tally" className="flex h-[52px] items-center gap-[8px] px-[12px]">
      {ties.map((t) => (
        <div key={t.key} className={CARD} data-tally={t.key}>
          <span className={LABEL}>{t.label}</span>
          <span>
            <Pill variant={running ? "muted" : "green"} size="tally">
              {running ? COPY.tally.pending : COPY.tally.tie}
            </Pill>
          </span>
        </div>
      ))}
      <div className={CARD} data-tally="late">
        <span className={LABEL}>{COPY.tally.lateDeposits}</span>
        <span>
          <Pill
            variant={running ? "muted" : late.length > 0 ? "amber" : "green-tint"}
            size="tally"
          >
            {running ? COPY.tally.pending : COPY.tally.late(late.length)}
          </Pill>
        </span>
      </div>
      <div className={CARD} data-tally="lost_earnings">
        <span className={LABEL}>{COPY.tally.lostEarnings}</span>
        <span className="text-[15px] tabular-nums">
          {running || first === undefined
            ? COPY.tally.pending
            : amount(first.lost_earnings, "cents").text}
        </span>
      </div>
      <div className={CARD} data-tally="receivable">
        <span className={LABEL}>{COPY.tally.receivable}</span>
        <span className="text-[15px] tabular-nums">
          {running || receivable === null ? COPY.tally.pending : amount(receivable, "cents").text}
        </span>
      </div>
    </div>
  );
}

function CardA({
  figures,
  running,
}: {
  figures: FiguresOut | undefined;
  running: boolean;
}): JSX.Element {
  return (
    <section data-ebp04="card-a" className={cn(BLOCK, "w-[506px]")}>
      <p className={BLOCK_HEAD}>{COPY.cardA}</p>
      {running || figures === undefined ? (
        <Skeleton className="m-[12px] h-[220px]" />
      ) : (
        <div className="flex flex-col py-[4px]">
          {figures.rows
            .filter((r) => !r.key.startsWith("tie."))
            .map((r) => (
              <div
                key={r.key}
                data-figure={r.key}
                className={cn(
                  "flex min-h-[30px] items-center gap-[8px] px-[14px] text-cell",
                  r.key.startsWith("total") && "font-medium border-t-[0.5px] border-stroke",
                )}
              >
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate">{r.label}</span>
                  {r.note !== null && r.note !== undefined && !r.key.startsWith("receivable") && (
                    <span className="truncate text-[11.5px] text-ink-3">{r.note}</span>
                  )}
                </span>
                {r.key.startsWith("receivable") && r.note !== null && r.note !== undefined && (
                  <Pill variant="amber" size="micro" data-entry-status>
                    {r.note}
                  </Pill>
                )}
                <Amount value={r.amount ?? ""} style="money" className="text-right" />
                {r.status === "tie" && (
                  <Pill variant="green" size="micro">
                    {COPY.tally.tie}
                  </Pill>
                )}
              </div>
            ))}
          {figures.total !== null && (
            <div
              data-figure="total"
              className="flex h-[32px] items-center justify-between border-y-[3px] border-double border-stroke px-[14px] text-cell font-medium"
            >
              <span>{figures.title}</span>
              <span className="tabular-nums">{money(figures.total)}</span>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Timeline({ payrolls }: { payrolls: readonly PayrollOut[] }): JSX.Element {
  return (
    <ol
      data-ebp04="timeline"
      aria-label={COPY.cardB(payrolls.length)}
      className="flex h-[36px] items-center justify-between px-[14px]"
    >
      {payrolls.map((p) => (
        <li
          key={p.id}
          data-dot={p.pay_date}
          data-late={p.late ? "true" : "false"}
          title={
            p.late && p.business_day_lag !== null ? COPY.daysLabel(p.business_day_lag) : p.pay_date
          }
          className={cn("size-[10px] rounded-full", p.late ? "bg-red" : "bg-green")}
        />
      ))}
    </ol>
  );
}

function PayrollTable({
  payrolls,
  onPayroll,
  totals,
}: {
  payrolls: readonly PayrollOut[];
  onPayroll?: ((id: string) => void) | undefined;
  totals?: { deferrals: string; match: string } | null | undefined;
}): JSX.Element {
  const fmt = useFormat();
  const C = COPY.columns;
  const head = "px-[8px] text-[11.5px] font-medium text-ink-3";
  return (
    <div data-ebp04="payrolls" className="flex flex-col">
      <div
        role="group"
        className="grid h-[28px] grid-cols-[100px_1fr_1fr_90px_80px_80px] items-center bg-nested"
      >
        <span className={head}>{C.payDate}</span>
        <span className={cn(head, "text-right")}>{C.deferrals}</span>
        <span className={cn(head, "text-right")}>{C.match}</span>
        <span className={head}>{C.deposited}</span>
        <span className={cn(head, "text-right")}>{C.days}</span>
        <span className={head}>{C.result}</span>
      </div>
      {payrolls.map((p) => (
        <button
          key={p.id}
          type="button"
          data-payroll={p.pay_date}
          data-late={p.late ? "true" : "false"}
          className={cn(
            "grid h-[28px] grid-cols-[100px_1fr_1fr_90px_80px_80px] items-center text-left text-cell hairline-b",
            p.late && "bg-sel-bg",
          )}
          onClick={() => {
            onPayroll?.(p.id);
          }}
        >
          <span className="px-[8px]">{fmt.date(p.pay_date, { withYear: true })}</span>
          <span className="px-[8px] text-right tabular-nums">{money(p.deferrals)}</span>
          <span className="px-[8px] text-right tabular-nums">{money(p.match)}</span>
          <span className="px-[8px]">
            {p.deposit_date === null ? "—" : fmt.date(p.deposit_date)}
          </span>
          <span className="px-[8px] text-right tabular-nums">{p.business_day_lag ?? "—"}</span>
          <span className="flex items-center gap-[4px] px-[8px]">
            {p.late ? (
              <>
                <Icon name="flag" size={12} className="text-red" />
                <Pill variant="red-tint" size="micro">
                  {COPY.late}
                </Pill>
              </>
            ) : (
              <Icon name="check" size={12} className="text-green" />
            )}
          </span>
        </button>
      ))}
      {totals != null && (
        <div
          role="group"
          data-ebp04="payrolls-total"
          className="grid h-[32px] grid-cols-[100px_1fr_1fr_90px_80px_80px] items-center border-t-[0.5px] border-stroke text-cell font-medium"
        >
          <span className="px-[8px]">{COPY.total}</span>
          <Amount value={totals.deferrals} style="money" className="px-[8px] text-right" />
          <Amount value={totals.match} style="money" className="px-[8px] text-right" />
          <span />
          <span />
          <span />
        </div>
      )}
    </div>
  );
}

function CardC({
  late,
  schedule,
}: {
  late: LateRemittanceOut;
  schedule: FiguresOut | undefined;
}): JSX.Element {
  const fmt = useFormat();
  const K = COPY.kv;
  const corrected = late.status === "corrected";
  return (
    <section data-ebp04="card-c" data-status={late.status} className={BLOCK}>
      <p className={BLOCK_HEAD}>{COPY.cardC}</p>
      <dl className="grid grid-cols-3 gap-x-[16px] gap-y-[6px] px-[14px] py-[10px] text-dense">
        <div>
          <dt className="text-ink-3">{K.principal}</dt>
          <dd className="tabular-nums">{money(late.amount)}</dd>
        </div>
        <div>
          <dt className="text-ink-3">{K.deposited}</dt>
          <dd>{fmt.date(late.deposited_on, { withYear: true })}</dd>
        </div>
        <div>
          <dt className="text-ink-3">{K.daysLate}</dt>
          <dd
            data-ebp04="days"
            className="tabular-nums"
          >{`${String(late.calendar_days)} · ${COPY.daysLabel(late.business_days)}`}</dd>
        </div>
        <div>
          <dt className="text-ink-3">{K.lostEarnings}</dt>
          <dd className="font-medium tabular-nums">{money(late.lost_earnings)}</dd>
        </div>
        <div>
          <dt className="text-ink-3">{K.correction}</dt>
          <dd>
            <Pill
              variant={corrected ? "green-tint" : "amber"}
              size="sm"
              data-correction={late.status}
            >
              {COPY.correction[late.status] ?? late.status}
            </Pill>
          </dd>
        </div>
        <div>
          <dt className="text-ink-3">{K.form5330}</dt>
          <dd>{COPY.form5330[late.form_5330] ?? late.form_5330}</dd>
        </div>
      </dl>
      {schedule !== undefined && (
        <div data-ebp04="4a" className="flex flex-col px-[14px] pb-[8px]">
          {schedule.rows.map((r) => (
            <div
              key={r.key}
              role="group"
              data-line={r.key}
              className="flex h-[28px] items-center justify-between text-cell hairline-b"
            >
              <span>{r.label}</span>
              <Amount value={r.amount ?? ""} style="whole" />
            </div>
          ))}
          <p className="pt-[8px] text-[11.5px] text-ink-3">{COPY.note4a}</p>
        </div>
      )}
    </section>
  );
}

/** EBP-04's canvas for the cockpit (AUD-02 renders it for `?section=ebp_04`). */
export function useContributionsCanvas(
  workItemId: string,
  options: ContributionsOptions,
): CockpitCanvas {
  const on = useFlag("ebp.modules") === true;
  const enabled = on && options.active;
  const path = { path: { work_item_id: workItemId } };
  const figures = useQuery({ ...ebpContributionsOptions(path), enabled });
  const payrolls = useQuery({ ...ebpPayrollsOptions(path), enabled });
  const late = useQuery({ ...ebpLateRemittancesOptions(path), enabled });
  const schedule = useQuery({ ...ebpSchedule4aOptions(path), enabled });
  const [own, setOwn] = useState<ContributionsTab>(options.tab ?? "reconciliation");
  const tab = options.tab ?? own;
  const running = options.running === true;

  let state: ViewState = { kind: "ready" };
  if (!on) state = { kind: "flag-off", flag: "ebp.modules" };
  else if (figures.isError) {
    const status = (figures.error as { status?: number } | null)?.status;
    state =
      status === 404
        ? { kind: "restricted", reason: "walled" }
        : { kind: "error", retry: () => void figures.refetch() };
  } else if (!running && (payrolls.data === undefined || late.data === undefined))
    state = { kind: "loading" };

  const rows = payrolls.data ?? [];
  const lates = late.data ?? [];
  const first = lates[0];
  const timely = rows.filter((p) => !p.late).length;
  // The tally's tie cards are the server's `tie.*` rows (Payroll → trust, Trust → FS, W-3 Box 12).
  const ties = (figures.data?.rows ?? [])
    .filter((r) => r.key.startsWith("tie.") && r.status === "tie")
    .map((r) => ({ key: r.key, label: r.label.toUpperCase() }));
  const receivable =
    (figures.data?.rows ?? []).find((r) => r.key.startsWith("receivable"))?.amount ?? null;
  // The table's foot is the server's figures: the browser sums nothing.
  const figureOf = (key: string) =>
    (figures.data?.rows ?? []).find((r) => r.key === key)?.amount ?? null;
  const deferralsTotal = figureOf("deferrals");
  const matchTotal = figureOf("match");
  const payrollTotals =
    deferralsTotal === null || matchTotal === null
      ? null
      : { deferrals: deferralsTotal, match: matchTotal };
  const canDraft = (schedule.data?.allowed_actions ?? []).includes("ebp_schedule.draft");

  return {
    title: COPY.title,
    state,
    actions: (
      <>
        <PaneAction icon="pencil" label={COPY.edit} />
        <PaneAction icon="check" label={COPY.signOff} />
        <PaneAction icon="file" label={COPY.sourceDocs} />
      </>
    ),
    controls: (
      <>
        <Segmented
          size="small"
          label={COPY.tabsLabel}
          options={[...COPY.tabs]}
          active={COPY.tabs[TABS.indexOf(tab)] ?? COPY.tabs[0]}
          onChange={(label) => {
            const next = TABS[COPY.tabs.findIndex((t) => t === label)];
            if (next === undefined) return;
            setOwn(next);
            options.onTab?.(next);
          }}
        />
        <span className="flex-1" />
        <Button variant="ghost" size="sm" icon="cloud-download">
          {COPY.openInExcel}
        </Button>
      </>
    ),
    children: (
      <div
        data-screen="EBP-04"
        data-tab={tab}
        className="flex flex-col gap-[12px] bg-shell pb-[12px]"
      >
        <Tally late={lates} receivable={receivable} ties={ties} running={running} />
        {tab === "testing" ? (
          <ContributionsTesting
            workItemId={workItemId}
            enabled={enabled}
            {...(options.onEligibility === undefined
              ? {}
              : { onEligibility: options.onEligibility })}
            {...(options.onDraft4a === undefined ? {} : { onDraft4a: options.onDraft4a })}
          />
        ) : tab === "timeliness" ? (
          <section className={cn(BLOCK, "mx-[12px]")}>
            <p className={BLOCK_HEAD}>{COPY.cardB(rows.length)}</p>
            <Timeline payrolls={rows} />
            <PayrollTable payrolls={rows} onPayroll={options.onPayroll} totals={payrollTotals} />
          </section>
        ) : (
          <>
            <div className="flex gap-[12px] px-[12px]">
              <CardA figures={figures.data} running={running} />
              <section data-ebp04="card-b" className={cn(BLOCK, "w-[506px]")}>
                <p className={BLOCK_HEAD}>{COPY.cardB(rows.length)}</p>
                <Timeline payrolls={rows} />
                {first !== undefined && (
                  <p data-ebp04="practice" className="px-[14px] pb-[8px] text-[12px] text-ink-2">
                    {COPY.practice(first.established_practice_days, timely, rows.length)}
                  </p>
                )}
                <PayrollTable
                  payrolls={rows.filter((p) => p.late)}
                  onPayroll={options.onPayroll}
                />
              </section>
            </div>
            {first !== undefined && (
              <div className="flex flex-col gap-[8px] px-[12px]">
                <CardC late={first} schedule={schedule.data} />
                <div className="flex items-center gap-[8px]">
                  {options.onRaise !== undefined && (
                    <Button variant="tonal" size="sm" onClick={options.onRaise}>
                      {COPY.raise}
                    </Button>
                  )}
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!canDraft}
                    onClick={options.onDraft4a}
                  >
                    {COPY.draft4a}
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    ),
  };
}
