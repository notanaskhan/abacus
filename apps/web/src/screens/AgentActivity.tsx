import type { ActivityOut } from "@abacus/api-client";
import {
  activityOptions,
  agentOptions,
  agentQueryKey,
  activityQueryKey,
  meOptions,
  pauseAgentMutation,
  resumeAgentMutation,
  teamOptions,
} from "@abacus/api-client/query";
import { Alert, Button, EmptyState, Input, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { isForbidden } from "../shell/mfa";

// SPEC-027 (TASK-050): each automatic action in plain words. References only, never content.
const ACTION: Record<string, string> = {
  "agent.started": "The engagement agent started",
  "agent.paused": "The agent was paused",
  "agent.resumed": "The agent was resumed",
  "agent.resume_checked": "Checked the engagement after resuming",
  "screening.start": "Screen new evidence",
  "screening.replayed": "Screened evidence that arrived while paused",
  "retrieval.start": "Retrieve from the client's system",
  "match.suggested": "Suggested request items for a file in the inbox",
  "agent.tick": "Daily check",
  "agent.self_paused": "The agent paused itself: the engagement has no active partner",
  "agent.self_resumed": "The agent resumed: the engagement has a partner again",
  "reminders.sent": "Sent overdue reminders",
  "reminders.drafted": "Drafted overdue reminders for you to send",
  "reminders.check": "Remind about overdue items",
  "reminders.restarted": "Due dates changed: reminders start again",
  "digest.sent": "Told the team about overdue items",
};
const REASON: Record<string, string> = {
  paused: "the agent is paused on this engagement",
  firm_paused: "your firm has paused every agent",
  advise: "your firm's autonomy is Advise, so a person starts it",
  agent_off: "the engagement agent is off for your firm",
  auto_retrieval_off: "automatic retrieval is off for your firm",
  not_open: "the engagement isn't open to client data yet",
  no_connection: "the client hasn't connected an accounting system",
  no_consenting_member: "no one who can retrieve has consented",
  nothing: "nothing was waiting for data",
  unavailable: "retrieval isn't available",
  malformed_event: "the event couldn't be read",
  self_paused: "the engagement has no active partner",
  no_partner: "the engagement has no active partner",
};

function describe(row: ActivityOut): string {
  const what = ACTION[row.action] ?? row.action;
  if (row.outcome === "done") {
    if (row.action === "match.suggested") {
      const n = row.item_count ?? 0;
      return `${what}: ${String(n)} ${n === 1 ? "suggestion" : "suggestions"}`;
    }
    if (row.action === "screening.replayed") return `${what} (${String(row.item_count ?? 0)})`;
    if (row.action === "reminders.sent" || row.action === "reminders.drafted")
      return `${what}: ${String(row.item_count ?? 0)} ${row.item_count === 1 ? "contact" : "contacts"}`;
    if (row.action === "digest.sent") return `${what}: ${String(row.item_count ?? 0)} overdue`;
    return what;
  }
  const why = row.reason != null ? (REASON[row.reason] ?? row.reason) : "";
  return row.outcome === "skipped"
    ? `Skipped: ${what.toLowerCase()}, because ${why}`
    : `Failed: ${what.toLowerCase()}`;
}

const TONE = { done: "success", skipped: "neutral", failed: "danger" } as const;

/** SPEC-027 AC-7: what happened automatically on this engagement, by which policy and why. */
export function AgentActivity({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const feed = useQuery({ ...activityOptions(path), retry: false });
  if (feed.isPending) return <Skeleton className="h-48" />;
  if (feed.isError) {
    return isForbidden(feed.error) ? (
      <Alert title="Not available">The activity feed is for the engagement&apos;s team.</Alert>
    ) : (
      <Alert title="Couldn't load the activity">{errorMessage(feed.error)}</Alert>
    );
  }
  if (feed.data.length === 0) {
    return (
      <EmptyState title="Nothing yet">
        When the engagement agent screens, retrieves or suggests something, it shows here.
      </EmptyState>
    );
  }
  return (
    <Panel title="Activity">
      <ol className="flex flex-col divide-y divide-line">
        {feed.data.map((row) => (
          <li key={row.id} className="flex flex-wrap items-center gap-3 py-2 text-sm">
            <span className="w-36 shrink-0 text-xs text-muted tabular-nums">
              {new Date(row.created_at).toLocaleString()}
            </span>
            <StatusPill tone={TONE[row.outcome]}>{row.policy}</StatusPill>
            <span>{describe(row)}</span>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

/** SPEC-027 AC-6: the engagement's pause switch (partner or manager) and the firm's state. */
export function AgentControls({ engagementId }: { engagementId: string }): JSX.Element | null {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const state = useQuery({ ...agentOptions(path), retry: false });
  const team = useQuery({ ...teamOptions(path), retry: false });
  const me = useQuery(meOptions());
  const [pausing, setPausing] = useState(false);
  const [reason, setReason] = useState("");
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: agentQueryKey(path) });
    void queryClient.invalidateQueries({ queryKey: activityQueryKey(path) });
  };
  const pause = useMutation({
    ...pauseAgentMutation(),
    onSuccess: () => {
      setPausing(false);
      setReason("");
      refresh();
    },
  });
  const resume = useMutation({ ...resumeAgentMutation(), onSuccess: refresh });
  if (state.data === undefined || !state.data.enabled) return null;
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role;
  const canSwitch = role === "engagement_partner" || role === "manager";
  const paused = state.data.paused_at != null;
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        {state.data.firm_paused_at != null ? (
          <StatusPill tone="warning">Agents paused by your firm</StatusPill>
        ) : paused ? (
          <StatusPill tone="warning">Agent paused</StatusPill>
        ) : (
          <StatusPill tone="success">Agent on</StatusPill>
        )}
        {paused && (
          <span className="text-muted">
            by {state.data.paused_by ?? "someone"}
            {state.data.reason != null && `: ${state.data.reason}`}
          </span>
        )}
        {canSwitch &&
          (paused ? (
            <Button
              size="sm"
              variant="ghost"
              disabled={resume.isPending}
              onClick={() => {
                resume.mutate(path);
              }}
            >
              Resume
            </Button>
          ) : !pausing ? (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setPausing(true);
              }}
            >
              Pause
            </Button>
          ) : (
            <>
              <Input
                aria-label="Why you're pausing (optional)"
                maxLength={300}
                placeholder="Why (optional)"
                value={reason}
                onChange={(e) => {
                  setReason(e.target.value);
                }}
              />
              <Button
                size="sm"
                disabled={pause.isPending}
                onClick={() => {
                  pause.mutate({ ...path, body: reason.trim() === "" ? {} : { reason } });
                }}
              >
                Pause the agent
              </Button>
            </>
          ))}
      </div>
      {(pause.isError || resume.isError) && (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(pause.error ?? resume.error)}
        </p>
      )}
    </div>
  );
}
