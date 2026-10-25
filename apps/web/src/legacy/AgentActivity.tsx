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
import {
  Alert,
  Button,
  EmptyState,
  Input,
  Panel,
  Skeleton,
  StatusPill,
  useFormat,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { isForbidden } from "../shell/mfa";
import { ACTION, REASON } from "../domain/agents/narrate";

export { narrate } from "../domain/agents/narrate";

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
  const fmt = useFormat();
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
      <ol className="flex flex-col divide-y divide-hair">
        {feed.data.map((row) => (
          <li key={row.id} className="flex flex-wrap items-center gap-3 py-2 text-[13px]">
            <span className="w-[132px] shrink-0 text-[12px] whitespace-nowrap text-ink-3 tabular-nums">
              {`${fmt.date(row.created_at)} ${fmt.time(row.created_at)}`}
            </span>
            <StatusPill tone={TONE[row.outcome]}>
              <span className="font-mono text-[10.5px]" title="The policy that acted (SPEC-027)">
                {row.policy}
              </span>
            </StatusPill>
            <span className={row.outcome === "skipped" ? "text-ink-2" : ""}>{describe(row)}</span>
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
      <div className="flex flex-wrap items-center gap-2 text-body">
        {state.data.firm_paused_at != null ? (
          <StatusPill tone="warning">Agents paused by your firm</StatusPill>
        ) : paused ? (
          <StatusPill tone="warning">Agent paused</StatusPill>
        ) : (
          <StatusPill tone="success">Agent on</StatusPill>
        )}
        {paused && (
          <span className="text-ink-3">
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
        <p role="alert" className="text-body text-danger">
          {errorMessage(pause.error ?? resume.error)}
        </p>
      )}
    </div>
  );
}
