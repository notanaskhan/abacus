import type { AgentRunOut, RunItemOut } from "@abacus/api-client";
import { listAgentRunsOptions } from "@abacus/api-client/query";
import {
  AgentBlocks,
  type AgentBlocksPayload,
  Button,
  count,
  EmptyState,
  Skeleton,
  StatusPill,
  useFormat,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { narrate } from "./narrate";
import { isActive, POLL_MS, useRunFeed } from "./runFeed";
import { duration, STATE, SUBJECT, TraceDrawer } from "./TraceDrawer";

// SHL-13 agent dock, first slice (P-09-T09; SPEC-318 AC-10): the engagement's runs as tool cards
// in the cockpit's 330 px Agent tab, oldest first like a thread. A pre-v2 run is one card
// (P-09 Story 8.1); expanding it follows the run live (Story 1.3) and "Open trace" opens WB-09.
// Read-only: approving or declining a proposal waits for P-10's C6 v2 actions (P-09-T14), so no
// control here decides anything (ADR-005; frontend rule 3).

/** The card title for a pre-v2 run: "Execute › ‹what it does›". */
export const TOOL: Readonly<Record<string, string>> = {
  "evidence.screener": "Execute › screen evidence",
  "evidence.upload_reviewer": "Execute › review upload",
  "evidence.matcher": "Execute › match inbox file",
  "requests.guidance_drafter": "Execute › draft guidance",
  "fieldwork.entry_assessor": "Execute › assess entries",
  "engagement.agent": "Execute › engagement check",
};

/** "citations:2,unverified:0" → "2 citations, 0 unverified". */
export function proposedWords(detail: string | null): string | null {
  if (detail === null || detail === "") return null;
  return detail
    .split(",")
    .map((pair) => {
      const [kind = "", n = "0"] = pair.split(":");
      return `${count(n)} ${kind.replaceAll("_", " ")}`;
    })
    .join(", ");
}

function CardBody({ run }: { run: AgentRunOut }): JSX.Element {
  const feed = useRunFeed(run.id);
  const card = feed.items.find((i) => i.kind === "tool_card");
  const proposed = proposedWords(card?.detail ?? null);
  const lines = feed.items.filter((i) => i.kind !== "tool_card");
  // Runtime v2 items carry server-validated AgentBlocks (P-09-T03); pre-v2 items carry none.
  const authored = feed.items.filter((i) => i.blocks != null);
  return (
    <dl className="grid grid-cols-[72px_1fr] gap-x-2 gap-y-1 pt-[6px] text-dense">
      <dt className="text-ink-3">Read</dt>
      <dd>{run.subject === null ? "—" : (SUBJECT[run.subject] ?? run.subject)}</dd>
      <dt className="text-ink-3">Proposed</dt>
      <dd>{proposed ?? "—"}</dd>
      <dt className="text-ink-3">Duration</dt>
      <dd className="tabular-nums">{duration(run.duration_ms)}</dd>
      {lines.length > 0 && (
        <>
          <dt className="text-ink-3">Then</dt>
          <dd>
            <ul>
              {lines.map((i) => (
                <li key={i.seq}>{lineWords(i)}</li>
              ))}
            </ul>
          </dd>
        </>
      )}
      {authored.map((i) => (
        <dd key={i.seq} className="col-span-2">
          <AgentBlocks blocks={i.blocks as AgentBlocksPayload} facts={{}} />
        </dd>
      ))}
    </dl>
  );
}

function lineWords(item: RunItemOut): string {
  if (item.kind === "narration") return narrate(item.code, item.outcome, item.detail);
  if (item.kind === "failure") return `Failed: ${item.code.replaceAll("_", " ")}`;
  const who = item.actor === null ? "" : ` by ${item.actor}`;
  return `${item.code.replaceAll("_", " ")}${who}`;
}

function ToolCard({
  run,
  onTrace,
}: {
  run: AgentRunOut;
  onTrace: (runId: string) => void;
}): JSX.Element {
  const fmt = useFormat();
  const [open, setOpen] = useState(false);
  const title = TOOL[run.agent] ?? run.agent_label;
  return (
    <li
      data-agent-card={run.state}
      className="rounded-pane border-[0.5px] border-hair bg-card p-[10px] text-dense"
    >
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-expanded={open}
          className="min-w-0 flex-1 truncate text-left font-medium"
          onClick={() => {
            setOpen(!open);
          }}
        >
          {title}
        </button>
        <StatusPill tone={STATE[run.state].tone}>{STATE[run.state].label}</StatusPill>
      </div>
      <p className="text-ink-3 tabular-nums">
        {`${run.agent_label} · ${fmt.time(run.started_at)} · ${run.initiator_name}`}
      </p>
      {open && <CardBody run={run} />}
      <div className="flex justify-end pt-[4px]">
        <Button
          size="xs"
          variant="ghost"
          onClick={() => {
            onTrace(run.id);
          }}
        >
          Open trace
        </Button>
      </div>
    </li>
  );
}

/** The Agent tab's run pane; `children` (the v1 activity list) stays below the thread. */
export function AgentDock({
  engagementId,
  children,
  onTrace,
}: {
  engagementId: string;
  children?: ReactNode;
  /** Open the trace elsewhere (a route's `useOpenTrace`), instead of the dock's own drawer. */
  onTrace?: (runId: string) => void;
}): JSX.Element {
  // A route may open the trace as its `?ov=run-trace` drawer; otherwise the dock holds it.
  const [trace, setTrace] = useState<string | null>(null);
  const showTrace = onTrace ?? setTrace;
  const runs = useQuery({
    ...listAgentRunsOptions({ path: { engagement_id: engagementId }, query: { limit: 10 } }),
    retry: false,
    refetchInterval: (q) => (q.state.data?.some((r) => isActive(r)) === true ? POLL_MS : false),
    refetchIntervalInBackground: false,
  });
  // The runs list answers 403 to anyone agent_run.read refuses: the dock then shows only children.
  const thread = runs.data === undefined ? [] : [...runs.data].reverse();
  return (
    <div data-agent-dock="runs" className="flex min-h-0 flex-1 flex-col overflow-y-auto">
      {runs.isPending ? (
        <Skeleton className="m-[12px] h-[96px]" />
      ) : runs.isError ? null : thread.length === 0 ? (
        <EmptyState icon="sparkles" title="No runs yet">
          When the agent screens, reviews or drafts something, its run shows here.
        </EmptyState>
      ) : (
        <ol aria-label="Agent runs" className="flex flex-col gap-[8px] p-[12px]">
          {thread.map((run) => (
            <ToolCard key={run.id} run={run} onTrace={showTrace} />
          ))}
        </ol>
      )}
      {children}
      {trace !== null && (
        <TraceDrawer
          runId={trace}
          onClose={() => {
            setTrace(null);
          }}
        />
      )}
    </div>
  );
}
