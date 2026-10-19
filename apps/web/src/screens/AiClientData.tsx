import type { AiClientDataOut } from "@abacus/api-client";
import {
  aiClientDataOptions,
  aiClientDataQueryKey,
  aiExclusionOptions,
  aiExclusionQueryKey,
  meOptions,
  setAiClientDataMutation,
  setAiExclusionMutation,
  teamOptions,
} from "@abacus/api-client/query";
import { Alert, Button, Label, Panel, Skeleton, StatusPill } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

// SPEC-036 (TASK-076): a firm opts in to AI on its clients' data against a disclosure generated
// from the provider terms register (ADR-114); each agent capability starts in shadow whose
// work isn't shown until promoted; an engagement partner can switch AI off for one engagement.

const STAGE_LABEL: Record<string, string> = {
  shadow: "Shadow (runs, not shown to your team yet)",
  live: "Live",
  off: "Off",
};

function Disclosure({ data }: { data: AiClientDataOut }): JSX.Element | null {
  const d = data.disclosure;
  if (d == null) return null;
  return (
    <dl className="flex flex-col gap-1 text-sm">
      <dt className="font-medium">Who runs it</dt>
      <dd className="text-muted">
        {d.provider}, in our own account, in the {d.region} region (United States).
      </dd>
      <dt className="font-medium">Your clients&apos; data</dt>
      <dd className="text-muted">
        Never used to train or improve models, and not kept after each request
        {d.retention_exceptions.length > 0 &&
          `, except ${d.retention_exceptions
            .map((x) => `${x.purpose} (up to ${String(x.max_days)} days)`)
            .join(", ")}`}
        .
      </dd>
      {d.subprocessors.length > 0 && (
        <>
          <dt className="font-medium">Subprocessors</dt>
          <dd className="text-muted">{d.subprocessors.join(", ")}</dd>
        </>
      )}
      <dt className="font-medium">Suggested wording for your engagement letters</dt>
      <dd className="text-muted">&ldquo;{d.letter_wording}&rdquo;</dd>
      <dt className="font-medium">Terms reviewed by</dt>
      <dd className="text-muted tabular-nums">{d.review_by}</dd>
    </dl>
  );
}

export function AiClientDataSetting({ canSet }: { canSet: boolean }): JSX.Element {
  const queryClient = useQueryClient();
  const state = useQuery({ ...aiClientDataOptions(), retry: false });
  const [read, setRead] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const change = useMutation({
    ...setAiClientDataMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(aiClientDataQueryKey(), data);
      setRead(false);
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  if (state.isPending) return <Skeleton className="h-40" />;
  if (state.isError) {
    if (isForbidden(state.error)) {
      return (
        <Panel title="AI on your clients' data">
          <p className="text-sm text-muted">Only firm administrators can see this setting.</p>
        </Panel>
      );
    }
    return <Alert title="Couldn't load this setting">{errorMessage(state.error)}</Alert>;
  }
  const data = state.data;
  const on = data.current;
  return (
    <Panel
      title="AI on your clients' data"
      action={
        on ? (
          <StatusPill tone="success">On</StatusPill>
        ) : (
          <StatusPill tone="neutral">Off</StatusPill>
        )
      }
    >
      <div className="flex flex-col gap-3">
        {!data.available ? (
          <p className="text-sm text-muted">
            Not available yet. The agent runs on synthetic data only until the provider terms are
            in place.
          </p>
        ) : (
          <>
            {data.lapsed && (
              <Alert title="The terms changed">
                Review what changed below and turn this on again to keep using AI on your
                clients&apos; data.
              </Alert>
            )}
            <Disclosure data={data} />
            {data.assistants.length > 0 ? (
              <ul aria-label="Agent capabilities" className="flex flex-col gap-1 text-sm">
                {data.assistants.map((a) => (
                  <li key={a.agent_id} className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{a.purpose}</span>
                    <StatusPill tone={a.stage === "live" ? "success" : "neutral"}>
                      {STAGE_LABEL[a.stage] ?? a.stage}
                    </StatusPill>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">No agent capabilities are available yet.</p>
            )}
            <p className="text-xs text-muted">
              Each capability starts in shadow: it runs, but your team doesn&apos;t see its work
              until we&apos;ve compared it with your team&apos;s decisions. Clients never see
              anything written by AI.
            </p>
            {canSet &&
              (on ? (
                <div>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={change.isPending}
                    onClick={() => {
                      change.mutate({ body: { on: false } });
                    }}
                  >
                    Turn off
                  </Button>
                </div>
              ) : (
                <div className="flex flex-wrap items-center gap-3 text-sm">
                  <label className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={read}
                      onChange={(e) => {
                        setRead(e.target.checked);
                      }}
                    />
                    I&apos;ve read how our clients&apos; data is handled
                  </label>
                  <Button
                    size="sm"
                    disabled={!read || change.isPending}
                    onClick={() => {
                      change.mutate({ body: { on: true } });
                    }}
                  >
                    Turn on
                  </Button>
                </div>
              ))}
          </>
        )}
        {change.error != null && !confirm && (
          <Alert title="Couldn't change this">
            {errorMessage(change.error) === "ai_client_data_unavailable"
              ? "Not available yet."
              : "That didn't work. Try again."}
          </Alert>
        )}
      </div>
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}

export function AiExclusionControl({
  engagementId,
}: {
  engagementId: string;
}): JSX.Element | null {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const state = useQuery({ ...aiExclusionOptions(path), retry: false });
  const team = useQuery({ ...teamOptions(path), retry: false });
  const me = useQuery(meOptions());
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const change = useMutation({
    ...setAiExclusionMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(aiExclusionQueryKey(path), data);
      setAsking(false);
      setReason("");
    },
  });
  if (state.data === undefined) return null;
  const role = team.data?.find((m) => m.user_id === me.data?.user_id)?.role;
  const canSwitch = role === "engagement_partner";
  const excluded = state.data.excluded;
  if (!excluded && !canSwitch) return null;
  return (
    <div className="flex flex-col gap-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        {excluded && (
          <>
            <StatusPill tone="warning">AI is off for this engagement</StatusPill>
            {state.data.reason != null && <span className="text-muted">{state.data.reason}</span>}
          </>
        )}
        {canSwitch &&
          (excluded ? (
            <Button
              size="sm"
              variant="ghost"
              disabled={change.isPending}
              onClick={() => {
                change.mutate({ ...path, body: { excluded: false } });
              }}
            >
              Turn AI back on
            </Button>
          ) : (
            !asking && (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setAsking(true);
                }}
              >
                Turn AI off for this engagement
              </Button>
            )
          ))}
      </div>
      {asking && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col gap-1">
            <Label htmlFor={`ai-off-${engagementId}`}>Why (for example, the client asked)</Label>
            <input
              id={`ai-off-${engagementId}`}
              maxLength={300}
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
              className="rounded-[var(--radius-control)] border border-line bg-surface p-2"
            />
          </div>
          <Button
            size="sm"
            disabled={reason.trim() === "" || change.isPending}
            onClick={() => {
              change.mutate({ ...path, body: { excluded: true, reason } });
            }}
          >
            Turn off
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              setAsking(false);
            }}
          >
            Cancel
          </Button>
        </div>
      )}
      {change.isError && (
        <Alert title="Couldn't change this">That didn&apos;t work. Try again.</Alert>
      )}
    </div>
  );
}
