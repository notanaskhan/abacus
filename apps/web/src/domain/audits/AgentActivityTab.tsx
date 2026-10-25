import type { ActivityOut } from "@abacus/api-client";
import {
  activityOptions,
  activityQueryKey,
  agentOptions,
  agentQueryKey,
  pauseAgentMutation,
} from "@abacus/api-client/query";
import { EmptyState, IconButton, Menu, Skeleton, StatusPill, useFormat } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { JSX } from "react";
import { AUDIT_MESSAGES } from "./messages";

// The cockpit dock's Agent tab, v1 (A-01-T12; AUD-02, DV-2): the engagement agent's activity,
// read-only, by policy and outcome in SPEC-027's words (references only, never content), with
// "Paused by ‹person›" while it is paused. "Pause agent" sits in the dock header menu and renders
// only with `agent.pause` (A-01 Story 2.3); the server refuses an agent context. P-09 replaces the
// body with the run pane (SHL-13) when engagement runs exist.

// SPEC-027 (TASK-050): each automatic action in plain words.
const ACTION: Readonly<Record<string, string>> = {
  "agent.started": "The engagement agent started",
  "agent.paused": "The agent was paused",
  "agent.resumed": "The agent was resumed",
  "agent.resume_checked": "Checked the engagement after resuming",
  "screening.start": "Screen new evidence",
  "screening.replayed": "Screened evidence that arrived while paused",
  "retrieval.start": "Retrieve from the client's system",
  "match.suggested": "Suggested request items for a file in the inbox",
  "agent.tick": "Daily check",
  "reminders.sent": "Sent overdue reminders",
  "reminders.drafted": "Drafted overdue reminders for you to send",
  "reminders.check": "Remind about overdue items",
  "digest.sent": "Told the team about overdue items",
  "upload_review.start": "Review an upload",
  "inbox_match.start": "Match a file in the inbox",
};

const TONE = { done: "success", skipped: "neutral", failed: "danger" } as const;

/** The data boundary refused AI for this firm (DF-04): the newest run failed on it. */
export function aiRefused(rows: readonly ActivityOut[]): boolean {
  const newest = rows[0];
  return newest !== undefined && newest.outcome !== "done" && newest.reason === "data_boundary";
}

function words(row: ActivityOut): string {
  const what = ACTION[row.action] ?? row.action;
  if (row.outcome === "done") return what;
  return row.outcome === "skipped"
    ? `Skipped: ${what.toLowerCase()}`
    : `Failed: ${what.toLowerCase()}`;
}

/** The v1 activity list; `aiUnavailable` is DockHost's DF-04 switch, read from the same rows. */
export function useAgentTab(engagementId: string) {
  const path = { path: { engagement_id: engagementId } };
  const feed = useQuery({ ...activityOptions(path), retry: false });
  const state = useQuery({ ...agentOptions(path), retry: false });
  return { feed, state, aiUnavailable: aiRefused(feed.data ?? []) };
}

export function AgentActivityTab({ engagementId }: { engagementId: string }): JSX.Element {
  const fmt = useFormat();
  const { feed, state } = useAgentTab(engagementId);
  if (feed.isPending) return <Skeleton className="m-[12px] h-[120px]" />;
  const pausedBy = state.data?.paused_at != null ? state.data.paused_by : null;
  return (
    <div data-audit-agent="activity" className="flex min-h-0 flex-1 flex-col gap-[9px] p-[12px]">
      {pausedBy != null && pausedBy !== "" && (
        <p role="status" className="text-dense text-ink-2">
          {AUDIT_MESSAGES.agent.paused(pausedBy)}
        </p>
      )}
      {(feed.data ?? []).length === 0 ? (
        <EmptyState icon="sparkles" title={AUDIT_MESSAGES.agent.empty}>
          {AUDIT_MESSAGES.agent.emptyBody}
        </EmptyState>
      ) : (
        <ol className="flex flex-col">
          {(feed.data ?? []).map((row) => (
            <li key={row.id} className="flex flex-col gap-[4px] py-[8px] text-dense hairline-b">
              <span className="flex items-center gap-[8px]">
                <StatusPill tone={TONE[row.outcome]} size="sm">
                  {row.policy}
                </StatusPill>
                <span className="text-meta text-ink-3 tabular-nums">
                  {`${fmt.date(row.created_at)} ${fmt.time(row.created_at)}`}
                </span>
              </span>
              <span className={row.outcome === "skipped" ? "text-ink-2" : "text-ink"}>
                {words(row)}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** The dock header menu: "Pause agent" (`agent.pause`), as the signed-in person. */
export function AgentDockMenu({ engagementId }: { engagementId: string }): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const pause = useMutation({
    ...pauseAgentMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: agentQueryKey(path) });
      void queryClient.invalidateQueries({ queryKey: activityQueryKey(path) });
    },
  });
  return (
    <Menu
      label={AUDIT_MESSAGES.agent.menu}
      trigger={<IconButton icon="ellipsis" label={AUDIT_MESSAGES.agent.menu} />}
      sections={[
        [
          {
            label: AUDIT_MESSAGES.agent.pause,
            icon: "pause",
            onSelect: () => {
              pause.mutate({ ...path, body: { reason: null } });
            },
          },
        ],
      ]}
    />
  );
}
