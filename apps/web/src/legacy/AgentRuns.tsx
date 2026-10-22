import type { AgentRunOut, RunTraceOut } from "@abacus/api-client";
import {
  agentRunTraceOptions,
  exportRunTraceMutation,
  listAgentRunsOptions,
} from "@abacus/api-client/query";
import {
  AgentText,
  Alert,
  Button,
  count,
  Drawer,
  EmptyState,
  Panel,
  ratio,
  Skeleton,
  StatusPill,
  type Tone,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

// SPEC-318 (TASK-461): a run's state in the status words, never a confidence figure (I-12).
export const STATE: Record<AgentRunOut["state"], { label: string; tone: Tone }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "info" },
  succeeded: { label: "Finished", tone: "success" },
  needs_input: { label: "Needs a person", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
};
const SUBJECT: Record<string, string> = {
  evidence_version: "An evidence version",
  inbox_file: "A file in the inbox",
  template_version: "A template version",
  task_scope: "Records in the run's scope",
};
const ROW_TONE: Record<RunTraceOut["rows"][number]["state"], Tone> = {
  done: "success",
  failed: "danger",
  waiting: "warning",
  running: "info",
};

/** Milliseconds as "850 ms", "4.2 s" or "3 min 5 s"; arithmetic only, no locale. */
export function duration(ms: number | null | undefined): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${count(ms)} ms`;
  if (ms < 60_000) return `${ratio(ms / 1000, 1)} s`;
  const s = Math.round(ms / 1000);
  return `${count(Math.floor(s / 60))} min ${count(s % 60)} s`;
}

/** SPEC-318 AC-1: the engagement's agent runs, newest first, each opening its trace. */
export function AgentRuns({ engagementId }: { engagementId: string }): JSX.Element | null {
  const fmt = useFormat();
  const [open, setOpen] = useState<string | null>(null);
  const runs = useQuery({
    ...listAgentRunsOptions({ path: { engagement_id: engagementId }, query: { limit: 25 } }),
    retry: false,
  });
  if (runs.isPending) return <Skeleton className="h-32" />;
  if (runs.isError) {
    return isForbidden(runs.error) ? null : (
      <Alert title="Couldn't load the agent runs">{errorMessage(runs.error)}</Alert>
    );
  }
  return (
    <Panel title="Agent runs">
      {runs.data.length === 0 ? (
        <EmptyState title="No runs yet">
          When the agent screens, reviews or drafts something, its run shows here.
        </EmptyState>
      ) : (
        <ol className="flex flex-col divide-y divide-hair">
          {runs.data.map((run) => (
            <li key={run.id} className="flex flex-wrap items-center gap-3 py-2 text-[13px]">
              <span className="w-[132px] shrink-0 text-[12px] whitespace-nowrap text-ink-3 tabular-nums">
                {`${fmt.date(run.started_at)} ${fmt.time(run.started_at)}`}
              </span>
              <StatusPill tone={STATE[run.state].tone}>{STATE[run.state].label}</StatusPill>
              <span className="font-medium">{run.agent_label}</span>
              <span className="text-ink-2">
                {run.subject == null ? "" : (SUBJECT[run.subject] ?? run.subject)}
              </span>
              <span className="text-ink-3 tabular-nums">{duration(run.duration_ms)}</span>
              <Button
                size="sm"
                variant="ghost"
                className="ml-auto"
                onClick={() => {
                  setOpen(run.id);
                }}
              >
                Open trace
              </Button>
            </li>
          ))}
        </ol>
      )}
      {open !== null && (
        <TraceDrawer
          runId={open}
          onClose={() => {
            setOpen(null);
          }}
        />
      )}
    </Panel>
  );
}

function download(filename: string, content: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** SPEC-318 AC-3: what the run did, step by step, computed from its records. */
export function TraceDrawer({
  runId,
  onClose,
}: {
  runId: string;
  onClose: () => void;
}): JSX.Element {
  const fmt = useFormat();
  const trace = useQuery({ ...agentRunTraceOptions({ path: { run_id: runId } }), retry: false });
  const [confirm, setConfirm] = useState(false);
  const exp = useMutation({
    ...exportRunTraceMutation(),
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
    onSuccess: (out) => {
      download(out.filename, out.content);
    },
  });
  const t = trace.data;
  // The run's own words: untrusted model text, rendered through AgentText only (ADR-065).
  const modelText = t?.model_text;
  return (
    <Drawer
      open
      width={480}
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      title={t?.run.agent_label ?? "Run trace"}
      meta={
        t && <StatusPill tone={STATE[t.run.state].tone}>{STATE[t.run.state].label}</StatusPill>
      }
      footer={
        <Button
          size="sm"
          variant="secondary"
          disabled={t === undefined || exp.isPending}
          onClick={() => {
            exp.mutate({ path: { run_id: runId }, body: { format: "json" } });
          }}
        >
          Export JSON
        </Button>
      }
    >
      {trace.isPending && <Skeleton className="h-48" />}
      {trace.isError && <Alert title="Couldn't load the trace">{errorMessage(trace.error)}</Alert>}
      {exp.isError && !confirm && (
        <Alert title="Couldn't export the trace">{errorMessage(exp.error)}</Alert>
      )}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
      {t && (
        <>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-[13px]">
            <dt className="text-ink-3">Started by</dt>
            <dd>{t.run.initiator_name}</dd>
            <dt className="text-ink-3">Duration</dt>
            <dd className="tabular-nums">{duration(t.run.duration_ms)}</dd>
            <dt className="text-ink-3">Model calls</dt>
            <dd className="tabular-nums">{t.attempts}</dd>
            <dt className="text-ink-3">Runtime</dt>
            <dd>{t.runtime}</dd>
            <dt className="text-ink-3">Region</dt>
            <dd>{t.region}</dd>
            <dt className="text-ink-3">Training</dt>
            <dd>{t.training}</dd>
          </dl>
          <section aria-label="Timeline">
            <h3 className="mb-1 text-[12px] font-medium text-ink-3">Timeline</h3>
            <ol className="flex flex-col divide-y divide-hair">
              {t.rows.map((row) => (
                <li key={row.seq} className="flex flex-wrap items-center gap-2 py-1.5 text-[13px]">
                  <span className="w-[64px] shrink-0 text-[12px] text-ink-3 tabular-nums">
                    {fmt.time(row.at)}
                  </span>
                  <StatusPill tone={ROW_TONE[row.state]}>{row.title}</StatusPill>
                  {row.detail != null && (
                    <span className="font-mono text-[11px] text-ink-2">{row.detail}</span>
                  )}
                  {row.actor != null && <span className="text-ink-2">{row.actor}</span>}
                </li>
              ))}
            </ol>
          </section>
          {t.output_counts.length > 0 && (
            <section aria-label="Output">
              <h3 className="mb-1 text-[12px] font-medium text-ink-3">Proposed</h3>
              <p className="text-[13px]">
                {t.output_counts
                  .map((c) => `${count(c.count)} ${c.kind.replaceAll("_", " ")}`)
                  .join(", ")}
              </p>
            </section>
          )}
          {modelText != null && (
            <section aria-label="The agent's words">
              <h3 className="mb-1 text-[12px] font-medium text-ink-3">The agent&apos;s words</h3>
              <AgentText text={modelText} />
            </section>
          )}
          {t.records_read.length > 0 && (
            <section aria-label="Records read">
              <h3 className="mb-1 text-[12px] font-medium text-ink-3">Records read</h3>
              <ul className="text-[13px]">
                {t.records_read.map((r) => (
                  <li key={r.source}>{`${SUBJECT[r.source] ?? r.source} (${count(r.count)})`}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </Drawer>
  );
}
