import type { TemplateDraftOut, TemplateItemOut } from "@abacus/api-client";
import {
  approveTemplateDraftsMutation,
  discardTemplateDraftsMutation,
  draftTemplateGuidanceMutation,
  getVersionQueryKey,
  listTemplatesQueryKey,
  publishDraftedMutation,
  templateDraftsOptions,
  templateDraftsQueryKey,
} from "@abacus/api-client/query";
import { AgentText, AiTag, Alert, Button, Label, Panel, Skeleton } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { ConfirmItsYou, isForbidden } from "../shell/mfa";

// SPEC-035 Q3 (TASK-074): drafts of why a standard request is asked and what good looks like,
// for a firm admin or practice leader to review on a template version. Approved text reaches
// engagements only when published as the template's next version (D2); drafts are shown through
// AgentText with the AI tag (ADR-065).

const REFUSED: Record<string, string> = {
  ai_drafting_unavailable: "Agent drafting isn't available here.",
  edited_draft_refused:
    "The edited text can't be used: remove amounts, dates, names, links or contact details.",
  read_not_confirmed: "Tick that you've read each draft first.",
  draft_already_decided: "Someone already decided on a draft. Refresh to see the latest.",
  nothing_to_publish: "Approve at least one draft first.",
  version_not_latest: "A newer version of this template exists. Draft on the latest version.",
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
  draft: TemplateDraftOut;
  item: TemplateItemOut | undefined;
  busy: boolean;
  onApprove: (why: string | null, good: string | null) => void;
  onDiscard: () => void;
}): JSX.Element {
  const [editing, setEditing] = useState(false);
  const [why, setWhy] = useState(draft.why);
  const [good, setGood] = useState(draft.good_looks_like);
  const approved = draft.status === "approved";
  return (
    <li className="flex flex-col gap-2 rounded-[var(--radius-control)] border border-stroke p-3 text-body">
      <span className="flex items-center gap-2">
        <AiTag />
        <span className="font-medium">{item?.description ?? "Standard request"}</span>
        {approved && <span className="text-meta text-ink-3">Approved, not yet published</span>}
      </span>
      {editing ? (
        <>
          <Label htmlFor={`why-${draft.id}`}>Why we need it</Label>
          <textarea
            id={`why-${draft.id}`}
            rows={2}
            maxLength={300}
            value={why}
            onChange={(e) => {
              setWhy(e.target.value);
            }}
            className="rounded-[var(--radius-control)] border border-hair bg-surface p-2"
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
            className="rounded-[var(--radius-control)] border border-hair bg-surface p-2"
          />
        </>
      ) : (
        <dl className="flex flex-col gap-1">
          <dt className="font-medium">Why we need it</dt>
          <dd className="text-ink-3">
            <AgentText text={draft.why} />
          </dd>
          <dt className="font-medium">What good looks like</dt>
          <dd className="text-ink-3">
            <AgentText text={draft.good_looks_like} />
          </dd>
        </dl>
      )}
      {(draft.effort != null || draft.blocks_fieldwork === true) && (
        <p className="text-meta text-ink-3">
          {draft.effort != null && `Suggested effort: ${draft.effort}`}
          {draft.effort_reason != null && ` (${draft.effort_reason})`}
          {draft.blocks_fieldwork === true && " · Suggests it blocks fieldwork"}
        </p>
      )}
      {!approved && (
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
              variant="secondary"
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
      )}
    </li>
  );
}

export function TemplateGuidanceDrafts({
  versionId,
  items,
}: {
  versionId: string;
  items: TemplateItemOut[];
}): JSX.Element | null {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const path = { path: { version_id: versionId } };
  const [asked, setAsked] = useState(false);
  const [read, setRead] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const drafts = useQuery({
    ...templateDraftsOptions(path),
    retry: false,
    refetchInterval: asked ? 4000 : false,
  });
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: templateDraftsQueryKey(path) });
  };
  const start = useMutation({
    ...draftTemplateGuidanceMutation(),
    onSuccess: () => {
      setAsked(true);
      refresh();
    },
  });
  const approve = useMutation({ ...approveTemplateDraftsMutation(), onSuccess: refresh });
  const discard = useMutation({ ...discardTemplateDraftsMutation(), onSuccess: refresh });
  const publish = useMutation({
    ...publishDraftedMutation(),
    onSuccess: (published) => {
      void queryClient.invalidateQueries({ queryKey: listTemplatesQueryKey() });
      void queryClient.invalidateQueries({ queryKey: getVersionQueryKey(path) });
      void navigate({
        to: "/admin/methodology/$versionId",
        params: { versionId: published.version_id },
      });
    },
    onError: (error) => {
      if (isForbidden(error)) setConfirm(true);
    },
  });
  if (drafts.isPending) return <Skeleton className="h-24" />;
  if (drafts.isError) {
    // Not allowed (only firm admins and practice leaders draft on templates): nothing to show.
    if (isForbidden(drafts.error)) return null;
    return <Alert title="Couldn't load drafts">{errorMessage(drafts.error)}</Alert>;
  }
  const without = items.filter((i) => !i.why && !i.good_looks_like).length;
  const pending = drafts.data.filter((d) => d.status === "pending");
  const approved = drafts.data.filter((d) => d.status === "approved");
  const busy = approve.isPending || discard.isPending || publish.isPending;
  const failed = start.error ?? approve.error ?? discard.error ?? (confirm ? null : publish.error);
  return (
    <Panel
      title="Guidance drafts"
      action={
        <Button
          size="sm"
          variant="secondary"
          disabled={start.isPending || without === 0}
          onClick={() => {
            start.mutate({ ...path, body: {} });
          }}
        >
          {`Draft guidance (${String(without)} without)`}
        </Button>
      }
    >
      {drafts.data.length === 0 ? (
        <p className="text-body text-ink-3">
          {asked ? "Drafting… drafts appear here as they're ready." : "No drafts to review."}
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <p className="text-meta text-ink-3">
            The agent drafted these from each standard request&apos;s description. Nothing changes
            until you approve and publish a new version; engagements on older versions keep theirs.
            Clients see approved drafts only if your firm allows it in settings.
          </p>
          <ul aria-label="Template drafts" className="flex flex-col gap-2">
            {[...pending, ...approved].map((d) => (
              <DraftCard
                key={d.id}
                draft={d}
                item={items[d.position]}
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
            <div className="flex flex-wrap items-center gap-3 text-body">
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
                variant="secondary"
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
          <div>
            <Button
              size="sm"
              disabled={approved.length === 0 || busy}
              onClick={() => {
                publish.mutate(path);
              }}
            >
              {`Publish as a new version (${String(approved.length)} approved)`}
            </Button>
          </div>
        </div>
      )}
      {failed !== null && <Alert title="Couldn't do that">{refusal(failed)}</Alert>}
      <ConfirmItsYou open={confirm} onOpenChange={setConfirm} />
    </Panel>
  );
}
