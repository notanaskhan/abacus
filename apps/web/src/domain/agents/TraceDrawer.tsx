import type { AgentRunOut, RunWriteOut } from "@abacus/api-client";
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
  EmptyState,
  Segmented,
  Skeleton,
  StatusPill,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { currentRoute, signIn } from "../../app-core/auth";
import { useOpenOverlay } from "../../app-core/open";
import { traceLink } from "./links";
import {
  RecordsReadTable,
  SummaryCard,
  Timeline,
  TimelineSkeleton,
  useMinimumLoading,
  WriteState,
} from "./TraceParts";
import { narrate } from "./narrate";
import { isActive, useRunFeed } from "./runFeed";

// WB-09 run trace drawer (P-09-T10; SPEC-318): moved from legacy/AgentRuns so the SHL-13 dock
// and the legacy Activity tab open the same drawer.

/** A 404 from a C6 read: another firm's run, a walled one or none (INV-3). */
function isNotFound(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    "detail" in error &&
    (error as { detail?: unknown }).detail === "not_found"
  );
}

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

import { STATE, SUBJECT } from "./traceWords";

export { duration, STATE, SUBJECT } from "./traceWords";

/** TASK-7825: JSON arrives as UTF-8 text, a PDF as base64 (C6 TraceExportOut). */
function download(
  filename: string,
  content: string,
  mediaType: string = "application/json",
  encoding: string = "utf-8",
): void {
  const data =
    encoding === "base64" ? Uint8Array.from(atob(content), (c) => c.charCodeAt(0)) : content;
  const url = URL.createObjectURL(new Blob([data], { type: mediaType }));
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
  // P-09-T10 remainder (DEC-3143): a proposal still waiting opens SHL-10 for a person, whose
  // server-side approval rights decide there; the drawer itself approves nothing.
  const openOverlay = useOpenOverlay();
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
            <>
              <WriteState write={w} />
              {w.state === "waiting" && w.kind === "proposal" && w.proposal_id != null && (
                <Button
                  size="xs"
                  variant="secondary"
                  onClick={() => {
                    // SHL-10 is `?ov=approve:<proposalRef>` (routes/to `ov.SHL10`).
                    if (w.proposal_id != null)
                      openOverlay({ key: "approve", args: [w.proposal_id] });
                  }}
                >
                  Approve…
                </Button>
              )}
            </>
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
  initialView = "Timeline",
  held = false,
}: {
  runId: string;
  onClose: () => void;
  /** The Segmented view open on arrival (WB-09 a3 Records read, a4 Writes & approvals). */
  initialView?: (typeof VIEWS)[number];
  /** Drawn in place, no layer (the gallery's parity frame, P-09-T18): the box its host gives. */
  held?: boolean;
}): JSX.Element {
  const trace = useQuery({ ...agentRunTraceOptions({ path: { run_id: runId } }), retry: false });
  const [confirm, setConfirm] = useState(false);
  const [view, setView] = useState<string>(initialView);
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
      download(out.filename, out.content, out.media_type, out.content_encoding);
    },
  });
  // WB-09 e: skeleton rows for at least 200 ms, never a half-filled summary.
  const loading = useMinimumLoading(trace.isPending);
  const t = loading ? undefined : trace.data;
  // The run's own words: untrusted model text, rendered through AgentText only (ADR-065).
  const modelText = t?.model_text;
  return (
    <Drawer
      open
      width={480}
      {...(held ? { forceState: "open" as const } : {})}
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
            Export trace (JSON)
          </Button>
          <Button
            size="sm"
            variant="secondary"
            disabled={t === undefined || exp.isPending}
            onClick={() => {
              exp.mutate({ path: { run_id: runId }, body: { format: "pdf" } });
            }}
          >
            Download PDF
          </Button>
          <span className="text-[11px] text-ink-3">
            Traces are kept with the firm audit log for 7 years.
          </span>
        </>
      }
    >
      {loading && !trace.isError && <TimelineSkeleton />}
      {trace.isError &&
        (isForbidden(trace.error) || isNotFound(trace.error) ? (
          <EmptyState icon="lock" title="You can't open this trace">
            It belongs to a run you can't see.
          </EmptyState>
        ) : (
          <Alert title="Couldn't load the trace">{errorMessage(trace.error)}</Alert>
        ))}
      {exp.isError && !confirm && (
        <Alert title="Couldn't export the trace">{errorMessage(exp.error)}</Alert>
      )}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
      {t && (
        <>
          <SummaryCard trace={t} live={live} />
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
              <Timeline runId={runId} rows={t.rows} metadata={t.projection === "metadata"} />
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
            <RecordsReadTable
              rows={t.records_read}
              label={(source) => SUBJECT[source] ?? source}
            />
          )}
          {view === "Writes & approvals" && <RunWrites runId={runId} />}
        </>
      )}
    </Drawer>
  );
}
