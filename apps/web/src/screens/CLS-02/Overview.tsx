// CLS-02 · Close › Overview (C-01-T34; docs/screens/CLS-02.md; handoff CLS-02 A–E): the close's
// home on T2 without a dock. The Summary rail reads the record (`GET /v1/closes/{id}`): the status
// pill and menu (In review… offered only at 21 of 21, On hold… a side flag, DF-23), stat rows,
// Details, Review and Delivery, and the Client Portal block. The canvas is the close run over C6
// v2 (`/runs`, `/runs/{n}`): the RunCard, the "Run n ⌄" history (an earlier run is read-only), the
// task groups with their `n of m` pills and rows, the inline decision card (D, answered only by
// the named person's click), a failed task's Retry and View run (E), and the composer to SHL-13.
// Every figure comes from the read model; the browser never sums money. Spinners are ink-2.
import type {
  CloseProcedureOut,
  CloseRunOut,
  CloseSummaryOut,
  CloseTaskGroupOut,
} from "@abacus/api-client";
import {
  closeRunOptions,
  closeRunsOptions,
  closeSummaryOptions,
  retryCloseProcedureMutation,
  startCloseRunMutation,
} from "@abacus/api-client/query";
import {
  Button,
  Icon,
  Menu,
  type MenuItem,
  QuestionCard,
  Skeleton,
  Spinner,
  StatusDisc,
  date,
  monthYear,
  time,
  useNow,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { OVERVIEW, completeWords, idleWords, progressWords } from "./overview-copy";

export type OverviewFrame = "a" | "b" | "c" | "d" | "e";
type RowState = "done" | "warn" | "run" | "todo" | "fail";

/** The frame a close's newest run puts the Overview in (the handoff's A to E). */
export function frameOfRun(run: CloseRunOut | undefined): OverviewFrame {
  if (run === undefined) return "c";
  if (run.status === "running") return "a";
  if (run.status === "needs_input") return "d";
  if (run.status === "failed") return "e";
  return "b";
}

export function rowStateOf(p: CloseProcedureOut): RowState {
  if (p.status === "running") return "run";
  if (p.status === "failed") return "fail";
  if (p.status === "queued") return "todo";
  if (p.status === "needs_attention" || (p.open_count ?? 0) > 0) return "warn";
  return "done";
}

/** A group's pill: done (done or with an open item) of all, and whether a row still runs. */
export function groupProgress(g: CloseTaskGroupOut): {
  done: number;
  total: number;
  running: boolean;
} {
  const states = g.procedures.map(rowStateOf);
  return {
    done: states.filter((s) => s === "done" || s === "warn").length,
    total: states.length,
    running: states.includes("run"),
  };
}

/** In review… is offered only when every account is reconciled (21 of 21). */
export function statusItems(
  summary: CloseSummaryOut,
  onMove: (to: "in_review" | "on_hold") => void,
): MenuItem[] {
  const allReconciled =
    summary.accounts_total > 0 && summary.accounts_reconciled === summary.accounts_total;
  return [
    {
      label: OVERVIEW.statusMenu.inReview,
      disabled: !allReconciled,
      ...(allReconciled ? {} : { hint: OVERVIEW.statusMenu.inReviewBlocked }),
      onSelect: () => {
        onMove("in_review");
      },
    },
    {
      label: OVERVIEW.statusMenu.onHold,
      onSelect: () => {
        onMove("on_hold");
      },
    },
    {
      label: OVERVIEW.handoffToTax,
      disabled: true,
      hint: OVERVIEW.handoffDisabled,
      onSelect: () => undefined,
    },
  ];
}

function minutesAgo(started: string, now: Date): string {
  const minutes = Math.max(0, Math.round((now.getTime() - new Date(started).getTime()) / 60000));
  return `Started ${String(minutes)} minutes ago`;
}

function timeOf(at: string): string {
  return time(at);
}

function Disc({ state }: { state: RowState }): JSX.Element {
  if (state === "run") return <Spinner size={15} label="Running" showLabel={false} />;
  return <StatusDisc state={state} size={17} />;
}

function StatRow({
  value,
  label,
  bad,
  onOpen,
}: {
  value: string;
  label: string;
  bad?: boolean;
  onOpen?: () => void;
}): JSX.Element {
  return (
    <button
      type="button"
      data-stat={label}
      onClick={onOpen}
      className="flex w-full items-center gap-[8px] px-[12px] pt-[9px] pb-[10px] text-left hairline-t hover:bg-nested"
    >
      <span className="flex min-w-0 flex-1 flex-col">
        <span className={`text-[15px] tabular-nums ${bad === true ? "text-red-ink" : ""}`}>
          {value}
        </span>
        <span className="text-[12px] text-ink-3">{label}</span>
      </span>
      <Icon name="chevron-right" size={12} className="text-ink-3" />
    </button>
  );
}

function Band({ title }: { title: string }): JSX.Element {
  return (
    <h3 className="flex h-[31px] items-center bg-band-hd px-[12px] text-[13.5px] font-medium">
      {title}
    </h3>
  );
}

function KV({ k, v, link }: { k: string; v: string; link?: boolean }): JSX.Element {
  return (
    <div className="flex h-[33px] items-center gap-[8px] px-[12px] hairline-t">
      <span className="flex-1 text-[13px] text-ink-2">{k}</span>
      <span className="truncate text-[13px]">{v}</span>
      {link === true ? <Icon name="chevron-right" size={12} className="text-ink-3" /> : null}
    </div>
  );
}

function monthName(period: string): string {
  return monthYear(period);
}

function dateWords(iso: string | null | undefined): string {
  if (iso === null || iso === undefined) return "—";
  return date(iso, { now: 0, withYear: true });
}

export interface CloseOverviewProps {
  closeId: string;
  /** The rendered instant (the demo clock in fixture mode). */
  now?: Date;
  onOpen?: (target: string) => void;
  onStatus?: (to: "in_review" | "on_hold") => void;
  onComposer?: () => void;
  onViewRun?: (runNo: number) => void;
  onAnswer?: (answer: unknown) => void;
}

function Rail({
  summary,
  props,
}: {
  summary: CloseSummaryOut;
  props: CloseOverviewProps;
}): JSX.Element {
  const open = (t: string): void => props.onOpen?.(t);
  const pct =
    summary.accounts_total === 0
      ? 0
      : Math.round((summary.accounts_reconciled * 100) / summary.accounts_total);
  const pastDue = summary.days_past_due ?? null;
  return (
    <aside
      aria-label={OVERVIEW.rail}
      style={{ width: 330 }}
      className="flex flex-none flex-col overflow-y-auto rounded-pane bg-card shadow-e2"
    >
      <h2 className="flex h-[46px] flex-none items-center justify-center text-[14.5px] font-medium hairline-b">
        {OVERVIEW.rail}
      </h2>
      <div className="flex flex-col items-center gap-[8px] px-[12px] pt-[14px] pb-[15px]">
        <span className="text-[14.5px] font-medium">{`${monthName(summary.period)} Close`}</span>
        <Menu
          label="Close status"
          trigger={
            <span
              data-status={summary.status}
              className="flex h-[25px] items-center gap-[4px] rounded-pill bg-amber-tint pr-[11px] pl-[13px] text-[12.5px] font-medium text-amber-ink"
            >
              {summary.status === "not_started" ? OVERVIEW.notStarted : "In progress"}
              <Icon name="chevron-down" size={12} className="opacity-55" />
            </span>
          }
          sections={[statusItems(summary, (to) => props.onStatus?.(to))]}
        />
      </div>
      <StatRow
        value={String(summary.open_issues)}
        label={OVERVIEW.stats.openIssues}
        onOpen={() => {
          open("CLS-06");
        }}
      />
      <StatRow
        value={String(summary.documents_in_binder)}
        label={OVERVIEW.stats.documents}
        onOpen={() => {
          open("CLS-03");
        }}
      />
      <StatRow
        value={`${String(pct)}% (${String(summary.accounts_reconciled)} / ${String(summary.accounts_total)})`}
        label={OVERVIEW.stats.reconciled}
        onOpen={() => {
          open("CLS-04");
        }}
      />
      {pastDue !== null && pastDue > 0 ? (
        <StatRow
          value={`${String(pastDue)} days`}
          label={`${OVERVIEW.stats.pastDue} (${dateWords(summary.due_on).replace(/, \d{4}$/, "")})`}
          bad
          onOpen={() => {
            open("HOME-03");
          }}
        />
      ) : (
        <StatRow value={dateWords(summary.due_on)} label={OVERVIEW.stats.due} />
      )}
      <Band title={OVERVIEW.details} />
      <KV k={OVERVIEW.detailRows.client} v={summary.client_name} link />
      <KV k={OVERVIEW.detailRows.engagement} v={summary.engagement_name} link />
      <KV k={OVERVIEW.detailRows.period} v={monthName(summary.period)} />
      <KV k={OVERVIEW.detailRows.plan} v={OVERVIEW.detailRows.planLink} link />
      <KV k={OVERVIEW.detailRows.files} v={summary.engagement_name} link />
      <Band title={OVERVIEW.review} />
      <KV k={OVERVIEW.reviewRows.due} v={dateWords(summary.due_on)} />
      <KV k={OVERVIEW.reviewRows.preparers} v={summary.preparer?.name ?? "—"} />
      <KV k={OVERVIEW.reviewRows.reviewers} v={summary.reviewer?.name ?? "—"} />
      <Band title={OVERVIEW.portal} />
      <KV k={OVERVIEW.portalRows.contact} v={summary.portal.contact_name ?? "—"} />
      <KV
        k={OVERVIEW.portalRows.status}
        v={summary.portal.portal_status === "active" ? "Active" : "Not invited"}
        link
      />
      <KV k={OVERVIEW.portalRows.portal} v={OVERVIEW.portalRows.portalLink} link />
      <KV
        k={OVERVIEW.portalRows.requests}
        v={`${String(summary.portal.requests_pending ?? 0)} pending`}
        link
      />
      <KV k={OVERVIEW.portalRows.reminder} v={OVERVIEW.portalRows.reminderLink} link />
    </aside>
  );
}

function RunCard({
  frame,
  run,
  summary,
  ready,
  now,
  onRun,
}: {
  frame: OverviewFrame;
  run: CloseRunOut | undefined;
  summary: CloseSummaryOut;
  ready: number;
  now: Date;
  onRun: () => void;
}): JSX.Element {
  const pct = run === undefined || run.total === 0 ? 0 : (run.done * 100) / run.total;
  const title =
    frame === "a"
      ? OVERVIEW.runningTitle
      : frame === "b"
        ? OVERVIEW.completeTitle
        : OVERVIEW.idleTitle;
  return (
    <div
      data-kit="RunCard"
      data-frame={frame}
      className="px-[16px] pt-[14px] pb-[13px] hairline-b"
    >
      <div className="flex items-start gap-[12px]">
        <div className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <h3 className="text-[15px] font-medium">{title}</h3>
          {frame === "a" ? (
            <p className="text-[12.5px] text-ink-3">{OVERVIEW.runningSub}</p>
          ) : null}
          {frame === "b" && run !== undefined ? (
            <p className="text-[12.5px] text-ink-3">
              {completeWords(
                run.total,
                run.open_issues,
                run.finished_at ? timeOf(run.finished_at) : "",
              )}
            </p>
          ) : null}
          {frame === "c" ? (
            <p className="text-[12.5px] text-ink-3">
              {idleWords(
                ready,
                0,
                summary.portal.requests_pending ?? 0,
                dateWords(summary.requests_publish_on).replace(/, \d{4}$/, ""),
              )}
            </p>
          ) : null}
          {frame === "d" ? (
            <p data-waiting className="flex items-center gap-[6px] text-[12.5px] text-ink-3">
              <span aria-hidden="true" className="size-[8px] rounded-pill bg-amber" />
              {OVERVIEW.waiting}
            </p>
          ) : null}
        </div>
        {frame === "c" ? (
          <Button variant="primary" size="lg" onClick={onRun}>
            <Icon name="play" size={12} />
            {OVERVIEW.runPrimary}
          </Button>
        ) : frame === "a" ? (
          <span className="flex size-[32px] items-center justify-center rounded-pill bg-card shadow-e1">
            <Spinner size={15} label="Running" showLabel={false} />
          </span>
        ) : frame === "b" ? (
          <span className="flex size-[32px] items-center justify-center rounded-pill bg-card shadow-e1">
            <StatusDisc state="done" size={15} />
          </span>
        ) : null}
      </div>
      {run !== undefined && (frame === "a" || frame === "b") ? (
        <div className="mt-[12px] flex items-center gap-[14px] text-[12.5px]">
          <span className="text-ink-2">{progressWords(run.done, run.total)}</span>
          <span
            role="progressbar"
            aria-valuenow={Math.round(pct)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={progressWords(run.done, run.total)}
            className="h-[3px] flex-1 rounded-pill bg-chip"
          >
            <span
              className="block h-full rounded-pill bg-espresso"
              style={{ width: `${String(Math.round(pct * 10) / 10)}%` }}
            />
          </span>
          {frame === "a" ? (
            <span className="text-ink-4">{minutesAgo(run.started_at, now)}</span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Group({
  group,
  readOnly,
  onRun,
  onRetry,
  onViewRun,
  onViewWork,
}: {
  group: CloseTaskGroupOut;
  readOnly: boolean;
  onRun: (scope: "group", key: string) => void;
  onRetry: (p: CloseProcedureOut) => void;
  onViewRun: () => void;
  onViewWork: (p: CloseProcedureOut) => void;
}): JSX.Element {
  const { done, total, running } = groupProgress(group);
  const open = group.procedures.reduce((n, p) => n + (p.open_count ?? 0), 0);
  return (
    <section data-group={group.key} aria-label={group.label}>
      <header className="flex items-center gap-[10px] bg-shell py-[10px] pr-[10px] pl-[13px]">
        <span className="flex min-w-0 flex-1 items-baseline gap-[8px]">
          <span className="text-[14px] font-medium">{group.label}</span>
          <span className="text-[12px] text-ink-3">
            {running ? OVERVIEW.running : open > 0 ? `${String(open)} open` : ""}
          </span>
        </span>
        <span
          data-badge={running ? "running" : "done"}
          className={`flex h-[21px] items-center gap-[5px] rounded-pill px-[8px] text-[11.5px] ${
            running ? "bg-chip text-ink-2" : "bg-green text-on-dark"
          }`}
        >
          {`${String(done)} of ${String(total)}`}
          {running ? (
            <Spinner size={10} label="Running" showLabel={false} />
          ) : (
            <Icon name="check" size={12} />
          )}
        </span>
        <Button
          variant="ghost"
          size="sm"
          disabled={readOnly || running}
          onClick={() => {
            onRun("group", group.key);
          }}
        >
          {OVERVIEW.run}
        </Button>
      </header>
      <ul>
        {group.procedures.map((p) => {
          const state = rowStateOf(p);
          return (
            <li
              key={p.procedure_id}
              data-procedure={p.procedure_id}
              data-state={state}
              className="flex items-start gap-[10px] bg-card pt-[8px] pr-[12px] pb-[9px] pl-[13px] hairline-t hover:bg-nested"
            >
              {state === "warn" ? (
                <Icon name="triangle-alert" size={15} className="text-amber" />
              ) : (
                <Disc state={state} />
              )}
              <div className="flex min-w-0 flex-1 flex-col gap-[2px]">
                <span className="text-[13.5px]">{p.label}</span>
                {state === "fail" ? (
                  <>
                    <span className="text-[12.5px] font-medium text-red-ink">
                      {OVERVIEW.failedTitle}
                    </span>
                    <span className="text-[12.5px] text-ink-2">
                      {p.failure ?? OVERVIEW.failedBody}
                    </span>
                  </>
                ) : (
                  <span className="text-[11.5px] text-ink-3">
                    {p.meta ?? (state === "todo" ? OVERVIEW.notStarted : "")}
                  </span>
                )}
              </div>
              {state === "fail" ? (
                <span className="flex gap-[6px]">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={readOnly}
                    onClick={() => {
                      onRetry(p);
                    }}
                  >
                    {OVERVIEW.retry}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={onViewRun}>
                    {OVERVIEW.viewRun}
                  </Button>
                </span>
              ) : (
                <span className="flex gap-[6px]">
                  {(p.open_count ?? 0) > 0 ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        onViewWork(p);
                      }}
                    >
                      {OVERVIEW.viewWork}
                    </Button>
                  ) : null}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

export function CloseOverview(props: CloseOverviewProps): JSX.Element {
  const clock = useNow();
  const now = props.now ?? new Date(clock);
  const summary = useQuery(closeSummaryOptions({ path: { close_id: props.closeId } }));
  const runs = useQuery(closeRunsOptions({ path: { close_id: props.closeId } }));
  const newest = runs.data?.items[0]?.run_no;
  const [picked, setPicked] = useState<number | null>(null);
  const runNo = picked ?? newest;
  const run = useQuery({
    ...closeRunOptions({ path: { close_id: props.closeId, run_no: runNo ?? 1 } }),
    enabled: runNo !== undefined,
  });
  const start = useMutation(startCloseRunMutation());
  const retry = useMutation(retryCloseProcedureMutation());
  if (summary.data === undefined || runs.data === undefined) {
    return (
      <div className="flex flex-1 items-center justify-center p-[20px]">
        <Skeleton className="h-[9px] w-[320px]" />
      </div>
    );
  }
  const data = summary.data;
  const current = runNo === undefined ? undefined : run.data;
  const frame = frameOfRun(current);
  const readOnly = current?.read_only === true;
  const startRun = (scope: "all" | "group" | "failed_only", key?: string): void => {
    start.mutate({
      path: { close_id: props.closeId },
      headers: { "Idempotency-Key": idempotencyKey() },
      body: { scope, ...(key === undefined ? {} : { group_key: key }) },
    });
  };
  return (
    <div
      data-screen="CLS-02"
      data-frame={frame}
      className="flex min-h-0 flex-1 gap-[10px] p-[10px]"
    >
      <Rail summary={data} props={props} />
      <section
        aria-label={OVERVIEW.canvas}
        className="relative flex min-w-0 flex-1 flex-col rounded-pane bg-card shadow-e2"
      >
        <header className="relative flex h-[46px] flex-none items-center justify-center text-[14.5px] font-medium hairline-b">
          {OVERVIEW.canvas}
          {runs.data.items.length > 0 ? (
            <span className="absolute right-[10px]">
              <Menu
                label="Run history"
                trigger={
                  <span className="flex items-center gap-[4px] text-[13.5px] font-normal text-ink-2">
                    {OVERVIEW.historyRun(runNo ?? 1)}
                    <Icon name="chevron-down" size={12} />
                  </span>
                }
                sections={[
                  runs.data.items.map((r): MenuItem => ({
                    label: OVERVIEW.historyRun(r.run_no),
                    checked: r.run_no === runNo,
                    onSelect: () => {
                      setPicked(r.run_no);
                    },
                  })),
                  [
                    {
                      label: OVERVIEW.runMenu.all,
                      disabled: frame === "a",
                      onSelect: () => {
                        startRun("all");
                      },
                    },
                    {
                      label: OVERVIEW.runMenu.failed,
                      disabled: frame !== "e",
                      onSelect: () => {
                        startRun("failed_only");
                      },
                    },
                  ],
                ]}
              />
            </span>
          ) : null}
        </header>
        <RunCard
          frame={frame}
          run={current}
          summary={data}
          ready={runs.data.ready_to_run ?? 0}
          now={now}
          onRun={() => {
            startRun("all");
          }}
        />
        <div className="min-h-0 flex-1 overflow-y-auto">
          {(current?.groups ?? []).map((g) => (
            <Group
              key={g.key}
              group={g}
              readOnly={readOnly}
              onRun={(_, key) => {
                startRun("group", key);
              }}
              onRetry={(p) => {
                retry.mutate({
                  path: {
                    close_id: props.closeId,
                    run_no: current?.run_no ?? 1,
                    step_id: p.run_step_id,
                  },
                  headers: { "Idempotency-Key": idempotencyKey() },
                });
              }}
              onViewRun={() => props.onViewRun?.(current?.run_no ?? 1)}
              onViewWork={() => props.onOpen?.("CLS-06")}
            />
          ))}
        </div>
        {frame === "d" ? (
          <div className="mx-[16px] mb-[9px]" data-decision>
            <QuestionCard
              question={OVERVIEW.decision}
              onAnswer={(a) => props.onAnswer?.(a)}
              {...(props.onComposer ? { onEscape: props.onComposer } : {})}
            />
          </div>
        ) : null}
        {frame === "a" ? (
          <div
            data-running-pill
            className="absolute bottom-[60px] left-1/2 flex h-[43px] -translate-x-1/2 items-center gap-[8px] rounded-pill bg-card px-[16px] shadow-e3"
          >
            <Spinner size={15} label="Running" showLabel={false} />
            <span className="text-[13px]">{OVERVIEW.runningPill}</span>
          </div>
        ) : null}
        <button
          type="button"
          data-composer
          onClick={props.onComposer}
          className="m-[10px] flex h-[38px] items-center gap-[8px] rounded-pill bg-card px-[12px] text-left text-[13px] text-ink-4 shadow-e1"
        >
          <Icon name="paperclip" size={14} className="text-ink-3" />
          {OVERVIEW.composer}
        </button>
      </section>
    </div>
  );
}
