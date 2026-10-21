import type { ReviewNoteOut } from "@abacus/api-client";
import {
  clearReviewNoteMutation,
  raiseReviewNoteMutation,
  reopenReviewNoteMutation,
  respondReviewNoteMutation,
  reviewMatrixQueryKey,
  reviewNotesOptions,
  reviewNotesQueryKey,
} from "@abacus/api-client/query";
import { Button, Skeleton, StatusPill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";

// SPEC-313 (TASK-331): review notes on a working paper or a trial balance, optionally on a cell
// or an account. Reviewers raise; anyone on the team answers; the raiser (or the partner)
// clears or reopens. An open or answered note blocks reviewer sign-offs and completion (G5).

export const RAISERS = new Set(["engagement_partner", "manager", "senior", "reviewer"]);
const RESPONDERS = new Set(["engagement_partner", "manager", "senior", "staff", "reviewer"]);
const STATUS: Record<
  ReviewNoteOut["status"],
  { label: string; tone: "warning" | "neutral" | "success" }
> = {
  open: { label: "Open", tone: "warning" },
  responded: { label: "Answered", tone: "neutral" },
  cleared: { label: "Cleared", tone: "success" },
};

export function openAnchors(notes: ReviewNoteOut[] | undefined): Set<string> {
  return new Set(
    (notes ?? [])
      .filter((n) => n.status !== "cleared" && n.anchor != null)
      .map((n) => n.anchor ?? ""),
  );
}

function errorWord(code: string): string {
  return (
    {
      not_the_raiser: "Only the reviewer who raised it, or the partner, can clear it.",
      review_note_state: "That note has moved on; reload to see it.",
      forbidden: "Your role can't do that.",
    }[code] ?? code
  );
}

export function ReviewableNotes({
  engagementId,
  targetType,
  targetId,
  anchor,
  anchorLabel,
  role,
}: {
  engagementId: string;
  targetType?: string | undefined;
  targetId?: string | undefined;
  anchor?: string | null | undefined;
  anchorLabel?: string | undefined;
  role: string;
}): JSX.Element {
  const queryClient = useQueryClient();
  const scoped = targetType !== undefined && targetId !== undefined;
  const options = reviewNotesOptions({
    path: { engagement_id: engagementId },
    ...(scoped ? { query: { target_type: targetType, target_id: targetId } } : {}),
  });
  const notes = useQuery({ ...options, retry: false });
  const [body, setBody] = useState("");
  const [pinned, setPinned] = useState(true);
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: reviewNotesQueryKey({ path: { engagement_id: engagementId } }),
    });
    void queryClient.invalidateQueries({
      queryKey: reviewMatrixQueryKey({ path: { engagement_id: engagementId } }),
    });
  };
  const fail = (e: unknown): void => {
    toast.show(errorWord(errorMessage(e)));
  };
  const raise = useMutation({
    ...raiseReviewNoteMutation(),
    onSuccess: () => {
      setBody("");
      refresh();
    },
    onError: fail,
  });
  if (notes.isPending) return <Skeleton className="h-16" />;
  if (notes.isError) return <p className="text-[12.5px] text-ink-3">Notes aren't available.</p>;
  const list = notes.data;
  const open = list.filter((n) => n.status !== "cleared").length;
  return (
    <div className="flex flex-col gap-2 text-[12.5px]">
      <p className="text-ink-3">
        {list.length === 0 ? "No review notes." : `${String(open)} open of ${String(list.length)}`}
      </p>
      <ul className="flex flex-col gap-2">
        {list.map((n) => (
          <NoteItem
            key={n.id}
            note={n}
            engagementId={engagementId}
            role={role}
            showTarget={!scoped}
            onDone={refresh}
            onError={fail}
          />
        ))}
      </ul>
      {scoped && RAISERS.has(role) && (
        <form
          className="flex flex-col gap-1.5 border-t-[0.5px] border-hair pt-2"
          onSubmit={(e) => {
            e.preventDefault();
            raise.mutate({
              path: { engagement_id: engagementId },
              body: {
                target_type: targetType,
                target_id: targetId,
                body: body.trim(),
                ...(pinned && anchor != null ? { anchor } : {}),
              },
            });
          }}
        >
          <textarea
            aria-label="New review note"
            value={body}
            maxLength={2000}
            placeholder="Raise a review note"
            onChange={(e) => {
              setBody(e.target.value);
            }}
            className="h-[60px] w-full rounded-tile border-0 bg-nested p-2 inset-shadow-hair"
          />
          <div className="flex items-center gap-2">
            {anchor != null && (
              <label className="flex items-center gap-1.5">
                <input
                  type="checkbox"
                  checked={pinned}
                  onChange={(e) => {
                    setPinned(e.target.checked);
                  }}
                />
                {`On ${anchorLabel ?? anchor}`}
              </label>
            )}
            <span className="flex-1" />
            <Button size="sm" type="submit" disabled={body.trim() === "" || raise.isPending}>
              Raise note
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

function NoteItem({
  note,
  engagementId,
  role,
  showTarget,
  onDone,
  onError,
}: {
  note: ReviewNoteOut;
  engagementId: string;
  role: string;
  showTarget: boolean;
  onDone: () => void;
  onError: (e: unknown) => void;
}): JSX.Element {
  const [reply, setReply] = useState("");
  const opts = {
    onSuccess: () => {
      setReply("");
      onDone();
    },
    onError,
  };
  const respond = useMutation({ ...respondReviewNoteMutation(), ...opts });
  const clear = useMutation({ ...clearReviewNoteMutation(), ...opts });
  const reopen = useMutation({ ...reopenReviewNoteMutation(), ...opts });
  const path = { path: { engagement_id: engagementId, note_id: note.id } };
  const canClose = note.raised_by_me || role === "engagement_partner";
  const word = STATUS[note.status];
  return (
    <li className="rounded-nested bg-card p-2 shadow-e1">
      <div className="flex flex-wrap items-center gap-1.5">
        <StatusPill tone={word.tone}>{word.label}</StatusPill>
        {showTarget && note.target_code != null && (
          <span className="font-medium tabular-nums">{note.target_code}</span>
        )}
        {note.anchor != null && (
          <span className="text-ink-3 tabular-nums">{`on ${note.anchor}`}</span>
        )}
        <span className="flex-1" />
        <span className="text-ink-3">{note.raised_by_name}</span>
      </div>
      <p className="mt-1 whitespace-pre-wrap">{note.body}</p>
      {note.events.map((e, i) => (
        <p key={i} className="mt-1 border-l-2 border-hair pl-2 text-ink-2">
          <span className="text-ink-3">{`${e.by_name} ${e.kind === "responded" ? "answered" : e.kind}: `}</span>
          {e.body}
        </p>
      ))}
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        {note.status !== "cleared" && RESPONDERS.has(role) && (
          <>
            <input
              aria-label={`Answer to ${note.body.slice(0, 30)}`}
              value={reply}
              maxLength={2000}
              placeholder="Answer"
              onChange={(e) => {
                setReply(e.target.value);
              }}
              className="h-[26px] min-w-0 flex-1 rounded-tile border-0 bg-nested px-2 inset-shadow-hair"
            />
            <Button
              size="sm"
              variant="secondary"
              disabled={reply.trim() === "" || respond.isPending}
              onClick={() => {
                respond.mutate({ ...path, body: { body: reply.trim() } });
              }}
            >
              Answer
            </Button>
          </>
        )}
        {note.status !== "cleared" && canClose && (
          <Button
            size="sm"
            variant="secondary"
            disabled={clear.isPending}
            onClick={() => {
              clear.mutate({ ...path, body: {} });
            }}
          >
            Clear
          </Button>
        )}
        {note.status === "cleared" && canClose && (
          <>
            <input
              aria-label="Why reopen"
              value={reply}
              maxLength={2000}
              placeholder="Why reopen"
              onChange={(e) => {
                setReply(e.target.value);
              }}
              className="h-[26px] min-w-0 flex-1 rounded-tile border-0 bg-nested px-2 inset-shadow-hair"
            />
            <Button
              size="sm"
              variant="ghost"
              disabled={reply.trim() === "" || reopen.isPending}
              onClick={() => {
                reopen.mutate({ ...path, body: { body: reply.trim() } });
              }}
            >
              Reopen
            </Button>
          </>
        )}
      </div>
    </li>
  );
}
