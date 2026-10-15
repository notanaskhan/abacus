import type { GuidanceDraftOut, RequestItemOut } from "@abacus/api-client";
import {
  approveDraftsMutation,
  discardDraftsMutation,
  draftGuidanceMutation,
  guidanceDraftsOptions,
  guidanceDraftsQueryKey,
  listRequestItemsQueryKey,
} from "@abacus/api-client/query";
import { AgentText, AiTag, Alert, Button, Label, Panel } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-035 (TASK-073): drafts of why a request is asked and what good looks like, for the firm to
// review. Nothing reaches an item until a person approves it (ADR-005); drafts are shown through
// AgentText with the AI tag (ADR-065).

const REFUSED: Record<string, string> = {
  ai_drafting_unavailable: "AI drafting isn't available here.",
  edited_draft_refused:
    "The edited text can't be used: remove amounts, dates, names, links or contact details.",
  read_not_confirmed: "Tick that you've read each draft first.",
  draft_already_decided: "Someone already decided on a draft. Refresh to see the latest.",
};

function refusal(error: unknown): string {
  return REFUSED[errorMessage(error)] ?? "That didn't work. Try again.";
}

function DraftCard({
  draft,
  item,
  busy,
  onApprove,
  onDiscard,
}: {
  draft: GuidanceDraftOut;
  item: RequestItemOut | undefined;
  busy: boolean;
  onApprove: (why: string | null, good: string | null) => void;
  onDiscard: () => void;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [why, setWhy] = useState(draft.why);
  const [good, setGood] = useState(draft.good_looks_like);
  return (
    <li className="flex flex-col gap-2 rounded-[var(--radius-control)] border border-ai-line p-3 text-sm">
      <span className="flex items-center gap-2">
        <AiTag />
        <span className="font-medium">{item?.description ?? "Request"}</span>
      </span>
      {editing ? (
        <>
          <Label htmlFor={`why-${draft.id}`}>Why we ask</Label>
          <textarea
            id={`why-${draft.id}`}
            rows={2}
            maxLength={300}
            value={why}
            onChange={(e) => {
              setWhy(e.target.value);
            }}
            className="rounded-[var(--radius-control)] border border-line bg-surface p-2"
          />
          <Label htmlFor={`good-${draft.id}`}>What good looks like</Label>
          <textarea
            id={`good-${draft.id}`}
            rows={3}
            maxLength={600}
            value={good}
            onChange={(e) => {
              setGood(e.target.value);
            }}
            className="rounded-[var(--radius-control)] border border-line bg-surface p-2"
          />
        </>
      ) : (
        <dl className="flex flex-col gap-1">
          <dt className="font-medium">Why we ask</dt>
          <dd className="text-muted">
            <AgentText text={draft.why} />
          </dd>
          <dt className="font-medium">What good looks like</dt>
          <dd className="text-muted">
            <AgentText text={draft.good_looks_like} />
          </dd>
        </dl>
      )}
      {(draft.effort != null || draft.blocks_fieldwork != null) && (
        <p className="text-xs text-muted">
          {draft.effort != null && `Suggested effort: ${draft.effort}`}
          {draft.effort_reason != null && ` (${draft.effort_reason})`}
          {draft.blocks_fieldwork === true && " · Suggests it blocks fieldwork"}
          {draft.blocks_reason != null &&
            draft.blocks_fieldwork === true &&
            ` (${draft.blocks_reason})`}
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          disabled={busy}
          onClick={() => {
            onApprove(editing ? why : null, editing ? good : null);
          }}
        >
          {editing ? "Approve edited" : "Approve"}
        </Button>
        {!editing && (
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={() => {
              setEditing(true);
            }}
          >
            Edit
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={busy} onClick={onDiscard}>
          Discard
        </Button>
      </div>
    </li>
  );
}

export function GuidanceDrafts({
  engagementId,
  items,
  canDraft,
}: {
  engagementId: string;
  items: RequestItemOut[];
  canDraft: boolean;
}): JSX.Element | null {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId } };
  const [asked, setAsked] = useState(false);
  const drafts = useQuery({
    ...guidanceDraftsOptions(path),
    retry: false,
    enabled: canDraft,
    refetchInterval: asked ? 4000 : false,
  });
  const [read, setRead] = useState(false);
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: guidanceDraftsQueryKey(path) });
    void queryClient.invalidateQueries({ queryKey: listRequestItemsQueryKey(path) });
  };
  const start = useMutation({
    ...draftGuidanceMutation(),
    onSuccess: () => {
      setAsked(true);
      refresh();
    },
  });
  const approve = useMutation({ ...approveDraftsMutation(), onSuccess: refresh });
  const discard = useMutation({ ...discardDraftsMutation(), onSuccess: refresh });
  if (!canDraft || drafts.isError) return null;
  const byId = new Map(items.map((i) => [i.id, i]));
  const without = items.filter((i) => !i.why && !i.good_looks_like).length;
  const pending = drafts.data ?? [];
  const busy = approve.isPending || discard.isPending;
  const failed = start.error ?? approve.error ?? discard.error;
  return (
    <Panel
      title="Client guidance drafts"
      action={
        <Button
          size="sm"
          variant="outline"
          disabled={start.isPending || without === 0}
          onClick={() => {
            start.mutate({ ...path, body: {} });
          }}
        >
          {`Draft guidance (${String(without)} without)`}
        </Button>
      }
    >
      {pending.length === 0 ? (
        <p className="text-sm text-muted">
          {asked ? "Drafting… drafts appear here as they're ready." : "No drafts to review."}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-xs text-muted">
            Drafted with AI from each request&apos;s description. Nothing changes until you
            approve. Clients see approved drafts only if your firm allows it in settings.
          </p>
          <ul aria-label="Drafts to review" className="flex flex-col gap-2">
            {pending.map((d) => (
              <DraftCard
                key={d.id}
                draft={d}
                item={byId.get(d.request_item_id)}
                busy={busy}
                onApprove={(why, good) => {
                  approve.mutate({
                    ...path,
                    body: { approvals: [{ draft_id: d.id, why, good_looks_like: good }] },
                  });
                }}
                onDiscard={() => {
                  discard.mutate({ ...path, body: { approvals: [{ draft_id: d.id }] } });
                }}
              />
            ))}
          </ul>
          {pending.length > 1 && (
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={read}
                  onChange={(e) => {
                    setRead(e.target.checked);
                  }}
                />
                I&apos;ve read each draft above
              </label>
              <Button
                size="sm"
                disabled={!read || busy}
                onClick={() => {
                  approve.mutate({
                    ...path,
                    body: {
                      approvals: pending.map((d) => ({ draft_id: d.id })),
                      confirmed_read: true,
                    },
                  });
                  setRead(false);
                }}
              >
                {`Approve all ${String(pending.length)}`}
              </Button>
            </div>
          )}
        </div>
      )}
      {failed !== null && <Alert title="Couldn't do that">{refusal(failed)}</Alert>}
    </Panel>
  );
}
