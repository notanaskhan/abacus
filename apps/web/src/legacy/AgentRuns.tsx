import { listAgentRunsOptions } from "@abacus/api-client/query";
import { Alert, Button, EmptyState, Panel, Skeleton, StatusPill, useFormat } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { isActive, POLL_MS } from "../domain/agents/runFeed";
import { duration, STATE, SUBJECT, TraceDrawer } from "../domain/agents/TraceDrawer";
import { errorMessage } from "../api";
import { isForbidden } from "../shell/mfa";

export { duration } from "../domain/agents/TraceDrawer";

/** SPEC-318 AC-1: the engagement's agent runs, newest first, each opening its trace. */
export function AgentRuns({ engagementId }: { engagementId: string }): JSX.Element | null {
  const fmt = useFormat();
  const [open, setOpen] = useState<string | null>(null);
  const runs = useQuery({
    ...listAgentRunsOptions({ path: { engagement_id: engagementId }, query: { limit: 25 } }),
    retry: false,
    // P-09 Story 1.3: keep the list current while any run is still going.
    refetchInterval: (q) => (q.state.data?.some((r) => isActive(r)) === true ? POLL_MS : false),
    refetchIntervalInBackground: false,
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
