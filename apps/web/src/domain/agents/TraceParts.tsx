import type {
  RecordsReadOut,
  RunTraceOut,
  RunWriteOut,
  TraceRowOut,
  TraceSummaryOut,
} from "@abacus/api-client";
import { agentRunTraceStepOptions } from "@abacus/api-client/query";
import {
  AgentText,
  count,
  Icon,
  ratio,
  type IconName,
  Skeleton,
  StatusPill,
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";

// WB-09 run trace drawer parts (P-09-T10; SPEC-648 Stories 4.1 to 4.3; handoff WB-09 a to e): the
// summary card, the timeline grammar with marks, a tool row's expansion (arguments and the first
// five records read, P-09-T08's step route), the records-read table with its Through column and
// total, and the writes with who they wait on. Every figure is the server's (ADR-050).

const TRIGGER: Readonly<Record<string, string>> = {
  manual: "Manual",
  schedule: "Schedule",
  agent_trigger: "Trigger",
  engagement_trigger: "Trigger",
  retry: "Retry",
  test: "Test",
  engagement_plan: "Engagement plan",
  agent_column: "Agent column",
  event_policy: "Policy",
};

/** "2 m 41 s", "17 m so far" for a live run, "1.9 s" under a minute. */
export function traceDuration(ms: number | null | undefined, live: boolean): string {
  if (ms == null) return "—";
  const total = Math.round(ms / 1000);
  const m = Math.floor(total / 60);
  const s = total % 60;
  const words =
    m === 0
      ? `${ratio(ms / 1000, 1)} s`
      : s === 0 || live
        ? `${count(m)} m`
        : `${count(m)} m ${count(s)} s`;
  return live ? `${words} so far` : words;
}

/** WB-09 summary: "0 done · 1 waiting". */
export function writesWords(s: TraceSummaryOut): string {
  return `${count(s.writes_done)} done · ${count(s.writes_waiting)} waiting`;
}

export function SummaryCard({ trace, live }: { trace: RunTraceOut; live: boolean }): JSX.Element {
  const fmt = useFormat();
  const s = trace.summary;
  const rows: [string, string][] = [];
  if (s != null) {
    if (s.run_number != null) rows.push(["Run", `Run #${String(s.run_number)}`]);
    rows.push(["Agent", s.agent_label]);
    const trigger =
      s.trigger_kind == null ? "" : ` (${TRIGGER[s.trigger_kind] ?? s.trigger_kind})`;
    rows.push(["Started", `${fmt.dateTime(s.started_at)}${trigger}`]);
    if (s.runs_as_name != null) rows.push(["Runs as", s.runs_as_name]);
    rows.push(["Duration", traceDuration(s.duration_ms, live)]);
    rows.push(["Records read", count(s.records_read)]);
    rows.push(["Citations", count(s.citations)]);
    rows.push(["Writes", writesWords(s)]);
  } else {
    rows.push(["Started by", trace.run.initiator_name]);
    rows.push(["Duration", traceDuration(trace.run.duration_ms, live)]);
  }
  rows.push(["Model", trace.runtime], ["Region", trace.region], ["Training", trace.training]);
  return (
    <dl
      data-trace-summary="true"
      className="grid grid-cols-[110px_1fr] gap-x-3 rounded-pane bg-card px-[12px] py-[6px] shadow-e1"
    >
      {rows.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="flex h-[30px] items-center text-[12.5px] text-ink-3">{k}</dt>
          <dd className="flex h-[30px] items-center text-[13px] tabular-nums">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

const MARK: Readonly<Record<string, { icon: IconName; className: string }>> = {
  start: { icon: "play", className: "bg-espresso text-on-dark" },
  plan: { icon: "list-checks", className: "bg-espresso text-on-dark" },
  done: { icon: "check", className: "bg-green text-on-dark" },
  running: { icon: "circle-dashed", className: "bg-nested text-ink-2" },
  waiting: { icon: "clock", className: "bg-amber-tint text-amber-ink" },
  blocked: { icon: "triangle-alert", className: "bg-amber-tint text-amber-ink" },
  failed: { icon: "x", className: "bg-red text-on-dark" },
  muted: { icon: "circle", className: "bg-nested text-ink-3" },
};
const MUTED_MARK: { icon: IconName; className: string } = {
  icon: "circle",
  className: "bg-nested text-ink-3",
};

function markOf(row: TraceRowOut): string {
  if (row.mark != null) return row.mark;
  return row.state === "failed" ? "failed" : row.state === "waiting" ? "waiting" : "done";
}

function StepExpansion({ runId, stepId }: { runId: string; stepId: string }): JSX.Element {
  const step = useQuery({
    ...agentRunTraceStepOptions({
      path: { run_id: runId, step_id: stepId },
      query: { records: 5 },
    }),
    retry: false,
  });
  if (step.isPending) return <Skeleton className="h-[40px]" />;
  if (step.isError) {
    return <p className="text-[12px] text-ink-3">The arguments for this step aren't available.</p>;
  }
  const args = step.data.args_summary;
  return (
    <div data-step-detail={stepId} className="pt-[4px] text-[12px] text-ink-2">
      {args != null && (
        <p>
          <AgentText text={args} />
        </p>
      )}
      {step.data.samples.length > 0 && (
        <ul aria-label="First records read" className="pt-[4px]">
          {step.data.samples.map((sample) => (
            <li key={sample.id}>
              <a className="underline-offset-2 hover:underline" href={sample.open_route}>
                {sample.label}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Timeline({
  runId,
  rows,
  metadata,
}: {
  runId: string;
  rows: readonly TraceRowOut[];
  metadata: boolean;
}): JSX.Element {
  const fmt = useFormat();
  const [open, setOpen] = useState<string | null>(null);
  return (
    <section aria-label="Timeline" className="rounded-pane bg-card px-[12px] py-[6px] shadow-e1">
      <ol className="flex flex-col">
        {rows.map((row) => {
          const mark = MARK[markOf(row)] ?? MUTED_MARK;
          const expandable = !metadata && row.step_id != null;
          const expanded = expandable && open === row.step_id;
          return (
            <li key={row.seq} data-trace-row={markOf(row)} className="flex gap-3 py-[6px]">
              <span className="w-[76px] shrink-0 text-right text-[12.5px] text-ink-2 tabular-nums">
                {fmt.time(row.at)}
              </span>
              <span
                aria-hidden="true"
                className={`flex size-[20px] shrink-0 items-center justify-center rounded-full ${mark.className}`}
              >
                <Icon name={mark.icon} size={12} />
              </span>
              <div className="min-w-0 flex-1">
                {expandable ? (
                  <button
                    type="button"
                    aria-expanded={expanded}
                    className="text-left text-[13.5px] font-medium"
                    onClick={() => {
                      setOpen(expanded ? null : (row.step_id ?? null));
                    }}
                  >
                    {row.title}
                  </button>
                ) : (
                  <p className="text-[13.5px] font-medium">{row.title}</p>
                )}
                {row.detail != null && (
                  <p
                    className={
                      markOf(row) === "failed"
                        ? "text-[12.5px] text-red-ink"
                        : "text-[12.5px] text-ink-2"
                    }
                  >
                    {row.detail}
                  </p>
                )}
                {row.actor != null && <p className="text-[12.5px] text-ink-2">{row.actor}</p>}
                {row.duration_ms != null && (
                  <p className="text-[11.5px] text-ink-3 tabular-nums">
                    {traceDuration(row.duration_ms, false)}
                  </p>
                )}
                {expanded && row.step_id != null && (
                  <StepExpansion runId={runId} stepId={row.step_id} />
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}

/** "Skeleton rows (9px bars) for 200ms+" (WB-09 e): never a half-filled summary. */
export function useMinimumLoading(loading: boolean, ms = 200): boolean {
  const [held, setHeld] = useState(true);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setHeld(false);
    }, ms);
    return () => {
      window.clearTimeout(timer);
    };
  }, [ms]);
  return loading || held;
}

export function TimelineSkeleton(): JSX.Element {
  return (
    <div data-trace-loading="true" aria-busy="true" className="flex flex-col gap-[10px] p-[12px]">
      {[0, 1, 2, 3, 4].map((n) => (
        <Skeleton key={n} className="h-[9px] w-full" />
      ))}
    </div>
  );
}

export function RecordsReadTable({
  rows,
  label,
}: {
  rows: readonly RecordsReadOut[];
  label: (source: string) => string;
}): JSX.Element {
  if (rows.length === 0) {
    return <p className="text-[13px] text-ink-2">This run recorded no records read.</p>;
  }
  const total = rows.reduce((n, r) => n + r.count, 0);
  return (
    <table aria-label="Records read" className="w-full text-[13px]">
      <thead>
        <tr className="text-left text-[12px] text-ink-3">
          <th className="font-normal">Source</th>
          <th className="text-right font-normal">Records</th>
          <th className="pl-3 font-normal">Through</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={`${r.source}:${r.connection_id ?? r.through ?? ""}`} className="h-[33px]">
            <td>{label(r.source)}</td>
            <td className="text-right tabular-nums">{count(r.count)}</td>
            <td className="pl-3 text-ink-2">
              {r.through ?? (r.connection_id != null ? "Firm connection" : "Accrued")}
            </td>
          </tr>
        ))}
        <tr className="h-[33px] border-t border-rule font-medium">
          <td>Total</td>
          <td className="text-right tabular-nums">{count(total)}</td>
          <td />
        </tr>
      </tbody>
    </table>
  );
}

/** WB-09 a4: a write's state pill; a waiting proposal names who it waits on. */
export function WriteState({ write }: { write: RunWriteOut }): JSX.Element | null {
  if (write.state === "waiting" || (write.state == null && write.decision == null)) {
    return (
      <StatusPill tone="warning">
        {write.approver_name != null ? `Waiting on ${write.approver_name}` : "Waiting on a person"}
      </StatusPill>
    );
  }
  if (write.state === "declined") return <StatusPill tone="neutral">Declined</StatusPill>;
  if (write.state === "superseded") return <StatusPill tone="neutral">Superseded</StatusPill>;
  return null;
}
