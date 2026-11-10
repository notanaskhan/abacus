// C-29 CommentThread v2 (P-05-T10; SHL-18 a–f; SPEC-650 AC-1 to AC-16): one anchor's thread in
// three hosts: the O1 popover (420), a dock tab (T20, 360) and a row-drawer tab (T18, 480).
//
// - Text is plain text only (ADR-109): mentions are tokens by weight and background.
// - Every comment's ··· menu offers Correct… (the author's own) and Redact… (with comment.redact),
//   never Edit or Delete (DF-18). The thread menu offers Copy link, Convert to to-do…, Convert to
//   review note… (allowed_actions has review_note.raise and the thread is internal; hidden on a
//   shared thread, SHL-18f) and Mute thread.
// - Resolve collapses the thread to its muted row with Reopen; nothing here touches a sign-off
//   (comments never block, R7).
// - The live container (`LiveCommentThread`) reads and writes through the generated client only.
import type {
  MentionCandidatesOut,
  ThreadCommentOut,
  ThreadEventOut,
  ThreadOut,
} from "@abacus/api-client";
import {
  convertToReviewNoteMutation,
  listCommentThreadsOptions,
  listCommentThreadsQueryKey,
  muteThreadMutation,
  openThreadMutation,
  postCommentMutation,
  reopenThreadMutation,
  resolveThreadMutation,
  threadMentionCandidatesOptions,
} from "@abacus/api-client/query";
import { EmptyState, Icon, Menu, type MenuItem, time } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { CommentComposer, type ComposerSubmit } from "./CommentComposer";
import { COPY } from "./copy";
import { segments } from "./mentions";

export type ThreadVariant = "popover" | "dock" | "drawer";

/** The host widths from the handoff: O1 420, T20 dock 360, T18 row drawer 480. */
export const VARIANT_WIDTH: Record<ThreadVariant, number> = {
  popover: 420,
  dock: 360,
  drawer: 480,
};

export interface CommentAnchor {
  anchor_kind: string;
  anchor_id: string;
  locator?: Record<string, string | number> | null;
}

export interface ThreadActions {
  onPost?: (value: ComposerSubmit) => void;
  onResolve?: () => void;
  onReopen?: () => void;
  onMute?: (muted: boolean) => void;
  onConvertToTodo?: () => void;
  onConvertToReviewNote?: () => void;
  onCopyLink?: () => void;
  onCorrect?: (commentId: string) => void;
  onRedact?: (commentId: string) => void;
  onClose?: () => void;
}

export interface CommentThreadViewProps extends ThreadActions {
  variant: ThreadVariant;
  thread: ThreadOut | null;
  /** The object chip ("Exceptions!A3 · Northwind PY2025"), used when there is no thread yet. */
  anchorLabel: string;
  /** The context row under the header (the row's own text and kind), when the host has one. */
  context?: { title: string; kind?: string };
  viewerId: string;
  candidates?: MentionCandidatesOut | undefined;
  engagementLabel: string;
  /** For a shared thread: the organisation that sees it ("Pruett & Lang LLP"). */
  sharedWith?: string;
  /** Open and resolved counts for the dock's segmented control. */
  counts?: { open: number; resolved: number };
  initialDraft?: string;
  /** Hold the resolved thread expanded (SHL-18d shows it under its muted row). */
  expandResolved?: boolean;
  /** The "@query" being typed, so the host can ask the server for matching candidates. */
  onMentionQuery?: (query: string | null) => void;
}

const clock = (at: string): string => time(at);

function Initials({ text }: { text: string }): JSX.Element {
  return (
    <span
      aria-hidden
      className="flex size-[20px] shrink-0 items-center justify-center rounded-pill bg-chip text-[10.5px] font-medium text-ink-2"
    >
      {text}
    </span>
  );
}

function Body({ text, names }: { text: string; names: string[] }): JSX.Element {
  return (
    <p className="whitespace-pre-wrap text-[12.5px] leading-[1.5] text-ink">
      {segments(text, names).map((part, i) =>
        part.mention ? (
          <span
            key={i}
            data-c29="mention"
            className="rounded-[4px] bg-sunken px-[3px] font-medium"
          >
            {part.text}
          </span>
        ) : (
          <span key={i}>{part.text}</span>
        ),
      )}
    </p>
  );
}

function namesOf(
  ids: readonly string[] | undefined,
  candidates: MentionCandidatesOut | undefined,
  body: string,
): string[] {
  if (!ids || ids.length === 0) return [];
  const known = new Map((candidates?.members ?? []).map((m) => [m.user_id, m.name]));
  const found = ids.map((id) => known.get(id)).filter((n): n is string => Boolean(n));
  if (found.length > 0) return found;
  // The candidates are the engagement's; a mention in an older comment still reads from its body.
  return Array.from(body.matchAll(/@([A-Z][\w'-]*(?: [A-Z][\w'-]*)?)/g), (m) => m[1] ?? "").filter(
    Boolean,
  );
}

function CommentRow({
  comment,
  viewerId,
  canRedact,
  candidates,
  onCorrect,
  onRedact,
}: {
  comment: ThreadCommentOut;
  viewerId: string;
  canRedact: boolean;
  candidates: MentionCandidatesOut | undefined;
  onCorrect?: ((id: string) => void) | undefined;
  onRedact?: ((id: string) => void) | undefined;
}): JSX.Element {
  const mine = comment.author.user_id === viewerId;
  const items: MenuItem[] = [];
  if (mine && !comment.redaction && onCorrect) {
    items.push({
      label: COPY.correct,
      opensDialog: true,
      onSelect: () => {
        onCorrect(comment.id);
      },
    });
  }
  if (canRedact && !comment.redaction && onRedact) {
    items.push({
      label: COPY.redact,
      opensDialog: true,
      onSelect: () => {
        onRedact(comment.id);
      },
    });
  }
  const mentioned = namesOf(comment.mentioned_user_ids, candidates, comment.body ?? "");
  return (
    <li data-c29="comment" data-comment-id={comment.id} className="flex flex-col gap-[4px]">
      <div className="flex items-center gap-[8px]">
        <Initials text={comment.author.initials} />
        <span className="text-[12.5px] font-medium text-ink">{comment.author.name}</span>
        <span className="text-[11px] text-ink-3">{clock(comment.created_at)}</span>
        {items.length > 0 ? (
          <span className="ml-auto">
            <Menu
              label={COPY.more}
              sections={[items]}
              trigger={
                <button
                  type="button"
                  aria-label={`${COPY.more}: ${comment.author.name}, ${clock(comment.created_at)}`}
                  className="flex size-[24px] items-center justify-center rounded-[6px] text-ink-3"
                >
                  <Icon name="ellipsis" size={14} />
                </button>
              }
            />
          </span>
        ) : null}
      </div>
      {comment.redaction ? (
        <p className="text-[12.5px] italic text-ink-3">
          {COPY.redactedBy(
            comment.redaction.redacted_by.name,
            comment.redaction.redacted_at.slice(0, 10),
            comment.redaction.reason,
          )}
        </p>
      ) : (
        <Body text={comment.body ?? ""} names={mentioned} />
      )}
      {comment.corrected_by_comment_id ? (
        <p className="text-[11px] text-ink-3">{COPY.correctedBelow}</p>
      ) : null}
      {mentioned.length > 0 && !comment.redaction ? (
        <p data-c29="delivery" className="flex items-center gap-[4px] text-[11px] text-ink-3">
          <Icon name="at-sign" size={12} />
          {COPY.notified(mentioned, clock(comment.created_at))}
        </p>
      ) : null}
    </li>
  );
}

function convertedEvent(
  events: readonly ThreadEventOut[] | undefined,
): ThreadEventOut | undefined {
  return events?.find((e) => e.kind === "converted" && e.ref_type === "review_note");
}

function resolvedEvent(events: readonly ThreadEventOut[] | undefined): ThreadEventOut | undefined {
  return [...(events ?? [])].reverse().find((e) => e.kind === "resolved");
}

export function CommentThreadView(props: CommentThreadViewProps): JSX.Element {
  const {
    variant,
    thread,
    anchorLabel,
    context,
    viewerId,
    candidates,
    engagementLabel,
    sharedWith,
    counts,
    initialDraft,
    expandResolved,
  } = props;
  const [expanded, setExpanded] = useState(expandResolved ?? false);
  const allowed = new Set(thread?.allowed_actions ?? ["comment.create"]);
  const shared = thread?.visibility === "shared";
  const resolved = thread?.status === "resolved";
  const threadMenu: MenuItem[] = [];
  if (thread) {
    if (props.onCopyLink) threadMenu.push({ label: COPY.copyLink, onSelect: props.onCopyLink });
    if (allowed.has("todo.create") && props.onConvertToTodo) {
      threadMenu.push({ label: COPY.toTodo, opensDialog: true, onSelect: props.onConvertToTodo });
    }
    if (allowed.has("review_note.raise") && !shared && props.onConvertToReviewNote) {
      threadMenu.push({
        label: COPY.toReviewNote,
        opensDialog: true,
        onSelect: props.onConvertToReviewNote,
      });
    }
    if (props.onMute) {
      const muted = thread.muted === true;
      threadMenu.push({
        label: muted ? COPY.unmute : COPY.mute,
        onSelect: () => props.onMute?.(!muted),
      });
    }
  }
  const converted = convertedEvent(thread?.events);
  const resolvedBy = resolvedEvent(thread?.events);
  const comments = thread?.comments ?? [];
  return (
    <section
      data-c29="thread"
      data-variant={variant}
      data-status={thread?.status ?? "none"}
      aria-label={`Comments on ${thread?.anchor.label ?? anchorLabel}`}
      style={{ width: VARIANT_WIDTH[variant] }}
      className={`flex flex-col bg-card ${variant === "popover" ? "rounded-[12px] shadow-e3" : ""}`}
    >
      {variant === "dock" && counts ? (
        <div
          className="flex items-center gap-[6px] px-[12px] py-[8px]"
          role="tablist"
          aria-label="Threads"
        >
          {COPY.openResolved(counts.open, counts.resolved).map((label, i) => (
            <span
              key={label}
              role="tab"
              aria-selected={(i === 1) === resolved}
              className={`rounded-[8px] px-[8px] py-[3px] text-[12px] ${(i === 1) === resolved ? "bg-sel-bg font-medium text-ink" : "text-ink-2"}`}
            >
              {label}
            </span>
          ))}
        </div>
      ) : null}
      <header className="flex h-[40px] items-center gap-[6px] border-b-[0.5px] border-hair px-[12px]">
        <span className="flex min-w-0 items-center gap-[4px] text-[11.5px] text-ink-3">
          <Icon name="table-2" size={12} />
          <span className="truncate">{thread?.anchor.label ?? anchorLabel}</span>
        </span>
        {shared && sharedWith ? (
          <span className="flex h-[22px] items-center gap-[4px] rounded-[6px] bg-amber-tint px-[6px] text-[11px] text-amber-ink">
            <Icon name="users" size={12} />
            {COPY.visibleTo(sharedWith)}
          </span>
        ) : null}
        <span className="ml-auto flex items-center gap-[2px]">
          {thread && !resolved && allowed.has("comment.resolve") && props.onResolve ? (
            <button
              type="button"
              onClick={props.onResolve}
              className="flex h-[28px] items-center gap-[4px] rounded-[8px] px-[8px] text-[12px] text-ink-2"
            >
              <Icon name="circle-check" size={13} />
              {COPY.resolve}
            </button>
          ) : null}
          {threadMenu.length > 0 ? (
            <Menu
              label={COPY.more}
              sections={[threadMenu]}
              trigger={
                <button
                  type="button"
                  aria-label={COPY.more}
                  className="flex size-[28px] items-center justify-center rounded-[8px] text-ink-2"
                >
                  <Icon name="ellipsis" size={14} />
                </button>
              }
            />
          ) : null}
          {variant === "popover" && props.onClose ? (
            <button
              type="button"
              aria-label={COPY.close}
              onClick={props.onClose}
              className="flex size-[26px] items-center justify-center rounded-[8px] text-ink-3"
            >
              <Icon name="x" size={14} />
            </button>
          ) : null}
        </span>
      </header>
      {context ? (
        <div className="flex h-[34px] items-center border-b-[0.5px] border-hair bg-surface px-[14px] text-[12px] text-ink-2">
          <span className="truncate">{context.title}</span>
          {context.kind ? (
            <span className="ml-auto text-[11.5px] text-ink-3">{context.kind}</span>
          ) : null}
        </div>
      ) : null}
      <div className="flex flex-1 flex-col gap-[10px] px-[14px] py-[12px]">
        {thread === null || comments.length === 0 ? (
          <EmptyState title={COPY.emptyTitle} icon="message-square">
            {COPY.emptyBody}
          </EmptyState>
        ) : (
          <>
            {resolved ? (
              <div className="flex h-[28px] items-center gap-[8px] rounded-[8px] bg-sunken px-[10px] text-[11.5px] text-ink-3">
                <button
                  type="button"
                  aria-expanded={expanded}
                  className="truncate text-left"
                  onClick={() => {
                    setExpanded((v) => !v);
                  }}
                >
                  {COPY.resolvedBy(
                    resolvedBy?.actor.name ?? "",
                    resolvedBy ? clock(resolvedBy.created_at) : "",
                    thread.comment_count,
                  )}
                </button>
                {props.onReopen ? (
                  <button type="button" className="ml-auto text-ink-2" onClick={props.onReopen}>
                    {COPY.reopen}
                  </button>
                ) : null}
              </div>
            ) : null}
            {resolved && !expanded ? null : (
              <ol className={`flex flex-col gap-[10px] ${resolved ? "text-ink-2" : ""}`}>
                {comments.map((comment) => (
                  <CommentRow
                    key={comment.id}
                    comment={comment}
                    viewerId={viewerId}
                    canRedact={allowed.has("comment.redact")}
                    candidates={candidates}
                    onCorrect={props.onCorrect}
                    onRedact={props.onRedact}
                  />
                ))}
              </ol>
            )}
          </>
        )}
        {converted ? <p className="text-[11px] text-ink-3">{COPY.converted}</p> : null}
      </div>
      {!resolved && props.onPost ? (
        <div className="border-t-[0.5px] border-hair px-[12px] pt-[10px] pb-[12px]">
          <CommentComposer
            candidates={candidates}
            engagementLabel={engagementLabel}
            {...(initialDraft === undefined ? {} : { initialText: initialDraft })}
            {...(shared && sharedWith ? { hint: COPY.sharedHint(sharedWith) } : {})}
            {...(props.onMentionQuery ? { onQuery: props.onMentionQuery } : {})}
            onSubmit={props.onPost}
          />
        </div>
      ) : null}
      <footer className="flex h-[36px] items-center gap-[4px] border-t-[0.5px] border-hair bg-surface px-[14px] text-[11px] text-ink-3">
        <Icon name="info" size={12} />
        {COPY.legend}
      </footer>
    </section>
  );
}

function locatorParam(locator: CommentAnchor["locator"]): string | null {
  if (!locator) return null;
  const sorted = Object.fromEntries(
    Object.entries(locator).sort(([a], [b]) => a.localeCompare(b)),
  );
  return JSON.stringify(sorted);
}

export interface LiveCommentThreadProps extends Omit<
  ThreadActions,
  "onPost" | "onResolve" | "onReopen" | "onMute" | "onConvertToReviewNote"
> {
  variant: ThreadVariant;
  anchor: CommentAnchor;
  anchorLabel: string;
  engagementId: string;
  engagementLabel: string;
  viewerId: string;
  context?: { title: string; kind?: string };
  sharedWith?: string;
  initialDraft?: string;
  expandResolved?: boolean;
}

/** The thread on one anchor from the server (the first open thread, else the latest resolved). */
export function LiveCommentThread(props: LiveCommentThreadProps): JSX.Element {
  const qc = useQueryClient();
  const query = {
    anchor_kind: props.anchor.anchor_kind,
    anchor_id: props.anchor.anchor_id,
    locator: locatorParam(props.anchor.locator),
  };
  const key = listCommentThreadsQueryKey({ query });
  const threads = useQuery(listCommentThreadsOptions({ query }));
  const [q, setQ] = useState<string | null>(null);
  const candidates = useQuery({
    ...threadMentionCandidatesOptions({
      path: { engagement_id: props.engagementId },
      ...(q ? { query: { q } } : {}),
    }),
    placeholderData: (previous) => previous,
  });
  const refresh = (): void => void qc.invalidateQueries({ queryKey: key });
  const open = useMutation({ ...openThreadMutation(), onSuccess: refresh });
  const post = useMutation({ ...postCommentMutation(), onSuccess: refresh });
  const resolve = useMutation({ ...resolveThreadMutation(), onSuccess: refresh });
  const reopen = useMutation({ ...reopenThreadMutation(), onSuccess: refresh });
  const mute = useMutation({ ...muteThreadMutation(), onSuccess: refresh });
  const convert = useMutation({ ...convertToReviewNoteMutation(), onSuccess: refresh });
  const items = threads.data?.items ?? [];
  const thread = items.find((t) => t.status === "open") ?? items.at(-1) ?? null;
  const counts = {
    open: items.filter((t) => t.status === "open").length,
    resolved: items.filter((t) => t.status === "resolved").length,
  };
  const onPost = (value: ComposerSubmit): void => {
    const body = {
      body: value.body,
      mention_user_ids: value.mentionUserIds,
      mention_team: value.mentionTeam,
    };
    if (thread && thread.status === "open") {
      post.mutate({ path: { thread_id: thread.id }, body });
    } else {
      open.mutate({
        body: { ...body, anchor: { ...props.anchor, locator: props.anchor.locator ?? null } },
      });
    }
  };
  const id = thread?.id;
  return (
    <CommentThreadView
      variant={props.variant}
      thread={thread}
      anchorLabel={props.anchorLabel}
      viewerId={props.viewerId}
      candidates={candidates.data}
      engagementLabel={props.engagementLabel}
      counts={counts}
      onPost={onPost}
      {...(props.context ? { context: props.context } : {})}
      {...(props.sharedWith ? { sharedWith: props.sharedWith } : {})}
      {...(props.initialDraft === undefined ? {} : { initialDraft: props.initialDraft })}
      {...(props.expandResolved ? { expandResolved: true } : {})}
      {...(props.onClose ? { onClose: props.onClose } : {})}
      {...(props.onCopyLink ? { onCopyLink: props.onCopyLink } : {})}
      {...(props.onConvertToTodo ? { onConvertToTodo: props.onConvertToTodo } : {})}
      {...(props.onCorrect ? { onCorrect: props.onCorrect } : {})}
      {...(props.onRedact ? { onRedact: props.onRedact } : {})}
      {...(id
        ? {
            onResolve: () => {
              resolve.mutate({ path: { thread_id: id } });
            },
            onReopen: () => {
              reopen.mutate({ path: { thread_id: id } });
            },
            onMute: (muted: boolean) => {
              mute.mutate({ path: { thread_id: id }, body: { muted } });
            },
            onConvertToReviewNote: () => {
              convert.mutate({ path: { thread_id: id } });
            },
          }
        : {})}
      onMentionQuery={setQ}
    />
  );
}
