import type { AgentRunOut, RunTraceOut, RunWriteOut } from "@abacus/api-client";
import {
  agentRunTraceOptions,
  agentRunTraceQueryKey,
  agentRunWritesOptions,
  exportRunTraceMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  Alert,
  Button,
  Dialog,
  count,
  Drawer,
  ratio,
  Segmented,
  Skeleton,
  StatusPill,
  type Tone,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { traceLink } from "./links";
import { narrate } from "./narrate";
import { isActive, useRunFeed } from "./runFeed";

// WB-09 run trace drawer (P-09-T10; SPEC-318): moved from legacy/AgentRuns so the SHL-13 dock
// and the legacy Activity tab open the same drawer.

/** A refusal for want of a recent sign-in, or by role: the body's `detail` is "forbidden". */
export function isForbidden(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    error.detail === "forbidden"
  );
}

function errorMessage(error: unknown): string {
  return isForbidden(error)
    ? "You don't have access to this run."
    : "Something went wrong. Try again.";
}

/** The step-up slot (ADR-030): a fresh sign-in, then back here (as ADM-01's). */
function ConfirmItsYou({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Confirm it's you"
      description="Exporting a trace needs a recent sign-in. Sign in again, then export once more. If it still isn't allowed, your role doesn't permit it."
    >
      <div className="flex justify-end gap-2">
        <Button
          variant="secondary"
          onClick={() => {
            onOpenChange(false);
          }}
        >
          Cancel
        </Button>
        <Button
          onClick={() => {
            signIn(currentRoute(), { forceLogin: true });
          }}
        >
          Sign in again
        </Button>
      </div>
    </Dialog>
  );
}

// SPEC-318 (TASK-461): a run's state in the status words, never a confidence figure (I-12).
export const STATE: Record<AgentRunOut["state"], { label: string; tone: Tone }> = {
  queued: { label: "Queued", tone: "neutral" },
  running: { label: "Running", tone: "info" },
  succeeded: { label: "Finished", tone: "success" },
  needs_input: { label: "Needs a person", tone: "warning" },
  failed: { label: "Failed", tone: "danger" },
};
export const SUBJECT: Record<string, string> = {
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

function download(filename: string, content: string): void {
  const url = URL.createObjectURL(new Blob([content], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** The run's state; "live" while the drawer is following it (P-09 Story 1.3). */
function RunPill({ state, live }: { state: AgentRunOut["state"]; live: boolean }): JSX.Element {
  return (
    <StatusPill tone={STATE[state].tone}>
      {live ? `${STATE[state].label} · live` : STATE[state].label}
    </StatusPill>
  );
}

// WB-09: the trace's three views (P-09-T10).
const VIEWS = ["Timeline", "Records read", "Writes & approvals"] as const;
const WRITE_KIND: Record<RunWriteOut["kind"], string> = {
  suggestion: "Suggestion",
  proposal: "Proposal",
  screening: "Screening",
};

/** C6 v1 (TASK-5000): what the run proposed to write, and who decided. Codes only. */
export function RunWrites({ runId }: { runId: string }): JSX.Element {
  const fmt = useFormat();
  const writes = useQuery({
    ...agentRunWritesOptions({ path: { run_id: runId } }),
    retry: false,
  });
  if (writes.isPending) return <Skeleton className="h-24" />;
  if (writes.isError) {
    return <Alert title="Couldn't load the writes">{errorMessage(writes.error)}</Alert>;
  }
  if (writes.data.length === 0) {
    return <p className="text-[13px] text-ink-2">This run proposed nothing to write.</p>;
  }
  return (
    <ol aria-label="Writes and approvals" className="flex flex-col divide-y divide-hair">
      {writes.data.map((w) => (
        <li key={w.id} className="flex flex-wrap items-center gap-2 py-1.5 text-[13px]">
          <span className="w-[64px] shrink-0 text-[12px] text-ink-3 tabular-nums">
            {fmt.time(w.at)}
          </span>
          <span className="font-medium">{WRITE_KIND[w.kind]}</span>
          <span className="font-mono text-[11px] text-ink-2">{w.key}</span>
          {w.decision == null ? (
            <StatusPill tone="warning">Waiting on a person</StatusPill>
          ) : (
            <span className="text-ink-2">
              {`${w.decision.replaceAll("_", " ")}${w.decided_by_name == null ? "" : ` by ${w.decided_by_name}`}`}
            </span>
          )}
        </li>
      ))}
    </ol>
  );
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
  const [view, setView] = useState<string>("Timeline");
  const client = useQueryClient();
  const feed = useRunFeed(runId);
  const live = isActive(feed.run);
  // A new item or a new state means the trace moved on: read it again.
  useEffect(() => {
    if (feed.lastSeq > 0) {
      void client.invalidateQueries({
        queryKey: agentRunTraceQueryKey({ path: { run_id: runId } }),
      });
    }
  }, [client, runId, feed.lastSeq, feed.run?.state]);
  const narration = feed.items.filter((i) => i.kind === "narration");
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
      meta={t && <RunPill state={(feed.run ?? t.run).state} live={live} />}
      footer={
        <>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              void navigator.clipboard.writeText(traceLink(runId, window.location.href));
            }}
          >
            Copy link
          </Button>
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
        </>
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
          {t.projection === "metadata" && (
            <p className="text-[13px] text-ink-2">You can see what ran, not the client content.</p>
          )}
          <Segmented
            size="small"
            label="Trace views"
            options={VIEWS}
            active={view}
            onChange={setView}
          />
          {view === "Timeline" && (
            <>
              <section aria-label="Timeline">
                <ol className="flex flex-col divide-y divide-hair">
                  {t.rows.map((row) => (
                    <li
                      key={row.seq}
                      className="flex flex-wrap items-center gap-2 py-1.5 text-[13px]"
                    >
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
              {narration.length > 0 && (
                <section aria-label="What the agent did">
                  <h3 className="mb-1 text-[12px] font-medium text-ink-3">What the agent did</h3>
                  <ul className="text-[13px]">
                    {narration.map((i) => (
                      <li key={i.seq}>{narrate(i.code, i.outcome, i.detail)}</li>
                    ))}
                  </ul>
                </section>
              )}
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
                  <h3 className="mb-1 text-[12px] font-medium text-ink-3">
                    The agent&apos;s words
                  </h3>
                  <AgentText text={modelText} />
                </section>
              )}
            </>
          )}
          {view === "Records read" && (
            <section aria-label="Records read">
              {t.records_read.length === 0 ? (
                <p className="text-[13px] text-ink-2">This run recorded no records read.</p>
              ) : (
                <ul className="text-[13px]">
                  {t.records_read.map((r) => (
                    <li
                      key={r.source}
                    >{`${SUBJECT[r.source] ?? r.source} (${count(r.count)})`}</li>
                  ))}
                </ul>
              )}
            </section>
          )}
          {view === "Writes & approvals" && <RunWrites runId={runId} />}
        </>
      )}
    </Drawer>
  );
}
