import type { CommentOut, MentionCandidateOut } from "@abacus/api-client";
import {
  itemCommentsOptions,
  itemCommentsQueryKey,
  listRequestItemsQueryKey,
  mentionCandidatesOptions,
  postItemCommentMutation,
  postVersionCommentMutation,
  readCommentsMutation,
  redactCommentMutation,
  versionCommentsOptions,
  versionCommentsQueryKey,
} from "@abacus/api-client/query";
import { Alert, Button, DateText, Dialog, Label, Skeleton } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useRef, useState } from "react";
import { errorMessage } from "../api";
import { isForbidden } from "../shell/mfa";
import { longDate } from "./importMessages";

// SPEC-032 (TASK-063; ADR-109): one thread, on a request item or one of its evidence versions.
// Comment text is shown as plain text only; internal notes look different from shared ones.

const LIMIT = 4000;
const REFUSED: Record<string, string> = {
  out_of_scope:
    "This mentions something outside this engagement (another client, another ledger's account or an amount not in it). Remove it, or post it as an internal note.",
  sharing_unavailable: "Sharing with the client isn't available right now.",
  mention_not_allowed: "Someone you mentioned can't see this comment.",
  correction_not_allowed: "That comment can't be corrected.",
  empty_comment: "Write something first.",
};

export type ThreadIds = { engagementId: string; itemId: string; versionId?: string | null };

function refusal(error: unknown): string {
  const code = errorMessage(error);
  return REFUSED[code] ?? "Couldn't post the comment. Try again.";
}

function Comment({
  comment,
  mine,
  canRedact,
  onCorrect,
  onRedact,
}: {
  comment: CommentOut;
  mine: boolean;
  canRedact: boolean;
  onCorrect: () => void;
  onRedact: () => void;
}): JSX.Element {
  const internal = comment.visibility === "internal";
  return (
    <li
      id={`comment-${comment.id}`}
      className={`flex flex-col gap-1 rounded-[var(--radius-control)] border p-3 text-body ${
        internal ? "border-line bg-warn-soft" : "border-line bg-surface"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-2 text-meta text-muted">
        <span className="font-medium text-ink">{comment.author_name || "Someone"}</span>
        <span>{comment.author_side === "client" ? "Client" : "Audit team"}</span>
        <DateText value={comment.created_at} kind="dateTime" />
        {internal && <span className="text-warn">Internal: the client can&apos;t see this</span>}
      </div>
      {comment.corrects != null && (
        <a href={`#comment-${comment.corrects}`} className="text-meta text-accent hover:underline">
          Corrects an earlier comment
        </a>
      )}
      {comment.redaction != null ? (
        <p className="text-muted italic">
          Redacted by {comment.redaction.redacted_by_name || "a firm administrator"} on{" "}
          {longDate(comment.redaction.redacted_at.slice(0, 10))}: {comment.redaction.reason}
        </p>
      ) : (
        <p className="whitespace-pre-wrap break-words">{comment.text}</p>
      )}
      {(comment.corrected_by ?? []).length > 0 && (
        <a
          href={`#comment-${comment.corrected_by?.[0] ?? ""}`}
          className="text-meta text-accent hover:underline"
        >
          Corrected below
        </a>
      )}
      {comment.redaction == null && (mine || canRedact) && (
        <div className="flex gap-3 text-meta">
          {mine && (
            <button type="button" className="text-accent hover:underline" onClick={onCorrect}>
              Correct
            </button>
          )}
          {canRedact && (
            <button type="button" className="text-danger hover:underline" onClick={onRedact}>
              Redact
            </button>
          )}
        </div>
      )}
    </li>
  );
}

function Mentions({
  ids,
  visibility,
  query,
  chosen,
  onPick,
}: {
  ids: ThreadIds;
  visibility: "internal" | "shared";
  query: string;
  chosen: MentionCandidateOut[];
  onPick: (person: MentionCandidateOut) => void;
}): JSX.Element | null {
  const candidates = useQuery({
    ...mentionCandidatesOptions({
      path: { engagement_id: ids.engagementId, item_id: ids.itemId },
      query: { visibility },
    }),
    retry: false,
  });
  const taken = new Set(chosen.map((c) => c.user_id));
  const matches = (candidates.data ?? []).filter(
    (c) => !taken.has(c.user_id) && c.display_name.toLowerCase().includes(query.toLowerCase()),
  );
  if (matches.length === 0) return null;
  return (
    <ul
      aria-label="People you can mention"
      className="flex flex-col rounded-[var(--radius-control)] border border-line bg-surface text-body"
    >
      {matches.slice(0, 8).map((c) => (
        <li key={c.user_id}>
          <button
            type="button"
            className="w-full px-3 py-1 text-left hover:bg-sunken"
            onClick={() => {
              onPick(c);
            }}
          >
            {c.display_name}{" "}
            <span className="text-meta text-muted">
              {c.side === "client" ? "Client" : "Audit team"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

export function CommentThread({
  ids,
  me,
  side,
  canShare,
  canRedact = false,
  label,
}: {
  ids: ThreadIds;
  me: string | undefined;
  side: "firm" | "client";
  canShare: boolean;
  canRedact?: boolean;
  label: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { engagement_id: ids.engagementId, item_id: ids.itemId };
  const versionId = ids.versionId ?? null;
  const key =
    versionId === null
      ? itemCommentsQueryKey({ path })
      : versionCommentsQueryKey({ path: { ...path, version_id: versionId } });
  const itemThread = useQuery({
    ...itemCommentsOptions({ path }),
    retry: false,
    enabled: versionId === null,
  });
  const versionThread = useQuery({
    ...versionCommentsOptions({ path: { ...path, version_id: versionId ?? "" } }),
    retry: false,
    enabled: versionId !== null,
  });
  const comments = versionId === null ? itemThread : versionThread;
  const [text, setText] = useState("");
  const [shared, setShared] = useState(side === "client");
  const [correcting, setCorrecting] = useState<CommentOut | null>(null);
  const [chosen, setChosen] = useState<MentionCandidateOut[]>([]);
  const [redacting, setRedacting] = useState<CommentOut | null>(null);
  const [reason, setReason] = useState("");
  const visibility = correcting?.visibility ?? (shared ? "shared" : "internal");

  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: key });
    void queryClient.invalidateQueries({
      queryKey: listRequestItemsQueryKey({ path: { engagement_id: ids.engagementId } }),
    });
  };
  const read = useMutation({ ...readCommentsMutation(), onSuccess: refresh });
  const opened = useRef(false);
  useEffect(() => {
    if (comments.isSuccess && !opened.current) {
      opened.current = true;
      read.mutate({ path, body: { evidence_version_id: versionId } });
    }
  }, [comments.isSuccess]);
  const done = (): void => {
    setText("");
    setChosen([]);
    setCorrecting(null);
    refresh();
  };
  const postItem = useMutation({ ...postItemCommentMutation(), onSuccess: done });
  const postVersion = useMutation({ ...postVersionCommentMutation(), onSuccess: done });
  const post = versionId === null ? postItem : postVersion;
  const redact = useMutation({
    ...redactCommentMutation(),
    onSuccess: () => {
      setRedacting(null);
      setReason("");
      refresh();
    },
  });

  const mention = /(?:^|\s)@([^\s@]*)$/.exec(text);
  const submit = (): void => {
    const body = {
      text,
      share: side === "firm" && visibility === "shared",
      corrects: correcting?.id ?? null,
      mentions: chosen.map((c) => c.user_id),
    };
    if (versionId === null) postItem.mutate({ path, body });
    else postVersion.mutate({ path: { ...path, version_id: versionId }, body });
  };

  if (comments.isPending) return <Skeleton className="h-16" />;
  if (comments.isError) {
    return isForbidden(comments.error) ? (
      <p className="text-body text-muted">You can&apos;t see these comments.</p>
    ) : (
      <Alert title="Couldn't load the comments">Try again in a moment.</Alert>
    );
  }
  const composer = `composer-${ids.itemId}-${versionId ?? "item"}`;
  return (
    <section aria-label={label} className="flex flex-col gap-3">
      {comments.data.length === 0 ? (
        <p className="text-body text-muted">No comments yet.</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {comments.data.map((c) => (
            <Comment
              key={c.id}
              comment={c}
              mine={c.author_user_id === me}
              canRedact={canRedact}
              onCorrect={() => {
                setCorrecting(c);
              }}
              onRedact={() => {
                setRedacting(c);
              }}
            />
          ))}
        </ol>
      )}
      <div className="flex flex-col gap-2">
        <Label htmlFor={composer}>
          {correcting !== null ? "Correcting your comment" : "Add a comment"}
        </Label>
        <textarea
          id={composer}
          rows={3}
          maxLength={LIMIT}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
          }}
          className={`rounded-[var(--radius-control)] border bg-surface p-2 text-body ${
            visibility === "shared" ? "border-stroke" : "border-line bg-warn-soft"
          }`}
        />
        {mention !== null && (
          <Mentions
            ids={ids}
            visibility={visibility}
            query={mention[1] ?? ""}
            chosen={chosen}
            onPick={(person) => {
              setChosen([...chosen, person]);
              setText(text.replace(/@([^\s@]*)$/, `@${person.display_name} `));
            }}
          />
        )}
        {chosen.length > 0 && (
          <p className="flex flex-wrap gap-1 text-meta" aria-label="Will be notified">
            {chosen.map((c) => (
              <span key={c.user_id} className="rounded-pill bg-accent-soft px-2 py-0.5">
                {c.display_name}
                <button
                  type="button"
                  aria-label={`Don't notify ${c.display_name}`}
                  className="ml-1"
                  onClick={() => {
                    setChosen(chosen.filter((x) => x.user_id !== c.user_id));
                  }}
                >
                  ×
                </button>
              </span>
            ))}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3 text-body">
          {side === "firm" && canShare && correcting === null && (
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={shared}
                onChange={(event) => {
                  setShared(event.target.checked);
                  setChosen([]);
                }}
              />
              Share with client
            </label>
          )}
          <span className="text-meta text-muted">
            {visibility === "shared"
              ? side === "firm"
                ? "The client will see this."
                : "Your auditor will see this."
              : "Internal note: only your team sees this."}
          </span>
          <span className="ml-auto text-meta text-muted tabular-nums">
            {text.length} / {LIMIT}
          </span>
          {correcting !== null && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setCorrecting(null);
              }}
            >
              Cancel
            </Button>
          )}
          <Button size="sm" disabled={text.trim() === "" || post.isPending} onClick={submit}>
            Post
          </Button>
        </div>
        {post.isError && (
          <p role="alert" className="text-body text-danger">
            {refusal(post.error)}
          </p>
        )}
      </div>
      <Dialog
        open={redacting !== null}
        onOpenChange={(next) => {
          if (!next) setRedacting(null);
        }}
        title="Redact comment"
      >
        <div className="flex flex-col gap-3 text-body">
          <p>
            The text will be hidden from everyone and replaced by your name, the date and this
            reason. This can&apos;t be undone.
          </p>
          <Label htmlFor="redact-reason">Reason</Label>
          <textarea
            id="redact-reason"
            rows={2}
            maxLength={500}
            value={reason}
            onChange={(event) => {
              setReason(event.target.value);
            }}
            className="rounded-[var(--radius-control)] border border-line bg-surface p-2"
          />
          <Button
            size="sm"
            variant="destructive"
            disabled={reason.trim() === "" || redact.isPending || redacting === null}
            onClick={() => {
              if (redacting !== null) {
                redact.mutate({
                  path: { ...path, comment_id: redacting.id },
                  body: { reason },
                });
              }
            }}
          >
            Redact
          </Button>
          {redact.isError && (
            <Alert title="Couldn't redact the comment">{errorMessage(redact.error)}</Alert>
          )}
        </div>
      </Dialog>
    </section>
  );
}
