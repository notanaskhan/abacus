"""Comments v2: threads on registered anchors (P-05-T05; SPEC-650 §3.1 to 3.5; ADR-236 proposed,
built dark behind `collaboration.v2`, DEC-3200).

- **Sealed and append-only.** A body is cleaned, limited to 4,000 characters, sealed per tenant
  (`kernel.crypto`) with its SHA-256 fingerprint, and never logged, put in an event, a
  notification or an audit reference. Nothing is edited or deleted: the author's Correct… posts a
  new comment naming the one it corrects; a firm administrator's Redact… (fresh MFA by the matrix)
  hides the text from every reader and keeps the sealed bytes.
- **Anchors.** A thread sits on `(anchor_kind, anchor_id, locator)` through the provider its
  owning module registered (`anchors.py`); an unknown kind is 409 before anything is read, and the
  caller's action is authorised on the provider's resource. One thread per anchor and locator, and
  per version only for a `pin` provider; the anchor's version is recorded when it opens.
- **Mentions.** Only people on the engagement who may read its comments (walls, independence);
  "@team" expands to them at post time without the author. One `mention.created` per person;
  notifications re-check membership at fan-out (AC-8).
- **Resolve, Reopen, Mute, Read, Share** are thread events (a person's, `actor_kind = 'human'`)
  in the same unit of work as their projection. A comment never blocks a sign-off and never enters
  the human-gate projection: only a review note does (R7, C3).
- **Share.** Only on a client-visible anchor (no anchor P-05 registers is one: 409
  `anchor_not_shareable`), with a grant scope that covers it, and every firm comment's text passes
  `communications.api.check_scope`.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.collaboration import repository as repo
from abacus.modules.collaboration.anchors import (
    AnchorFacts,
    AnchorNotShareable,
    AnchorScopeMismatch,
    Locator,
    anchor_facts,
    locator_key,
    provider_of,
)
from abacus.modules.collaboration.candidates import mentionable
from abacus.modules.collaboration.errors import (
    AlreadyRedacted,
    CommentTooLong,
    CorrectionNotAllowed,
    EmptyComment,
    MentionNotAllowed,
    ThreadAlreadyResolved,
    ThreadNotResolved,
)
from abacus.modules.collaboration.events import (
    CommentCreated,
    MentionCreated,
    ThreadReopened,
    ThreadResolved,
)
from abacus.modules.collaboration.models import CommentThread
from abacus.modules.communications.api import check_scope
from abacus.modules.engagements.api import EngagementRef, get_ref
from abacus.modules.identity.api import AuthContext, Forbidden, allowed_actions, authorise

MAX_BODY: Final = 4000
MAX_REASON: Final = 500
THREAD_ACTIONS: Final = (
    "comment.create",
    "comment.resolve",
    "comment.share",
    "comment.redact",
    "todo.create",
)  # `review_note.raise` joins with P-05-T09's conversion route


class CommentOutOfScope(DomainConflict):
    """Shared firm text names something outside the engagement (SPEC-032 Q4)."""

    code = "out_of_scope"


class ShareScopeInvalid(DomainInvalid):
    """The grant scope does not cover the anchor (C5)."""

    code = "share_scope_invalid"


@dataclass(frozen=True)
class RedactionView:
    redacted_by: UUID
    redacted_at: datetime
    reason: str


@dataclass(frozen=True)
class CommentView:
    id: UUID
    author_user_id: UUID
    author_side: str
    body: str | None  # None once redacted
    corrects_comment_id: UUID | None
    corrected_by_comment_id: UUID | None
    mentioned_user_ids: list[UUID]
    citation_ids: list[UUID]
    redaction: RedactionView | None
    created_at: datetime


@dataclass(frozen=True)
class EventView:
    kind: str
    actor_user_id: UUID
    ref_type: str | None
    ref_id: UUID | None
    created_at: datetime


@dataclass(frozen=True)
class ThreadView:
    id: UUID
    anchor_kind: str
    anchor_id: UUID
    locator: dict[str, str | int] | None
    facts: AnchorFacts
    engagement_id: UUID
    status: str
    visibility: str
    opened_on_version_no: int | None
    pinned_version_no: int | None
    last_comment_at: datetime | None
    comments: list[CommentView]
    events: list[EventView]
    unread: bool
    muted: bool
    allowed_actions: list[str]


@dataclass(frozen=True)
class Posted:
    thread_id: UUID
    comment_id: UUID
    notified: list[UUID] = field(default_factory=list[UUID])


@dataclass(frozen=True)
class AnchorCount:
    anchor_kind: str
    anchor_id: UUID
    locator: dict[str, str | int] | None
    open: int
    resolved: int
    unread: int


def clean_text(text: str, limit: int, *, too_long: type[DomainInvalid] = CommentTooLong) -> str:
    """Plain text: control characters other than line breaks and tabs removed, trimmed."""
    kept = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C").strip()
    if not kept:
        raise EmptyComment
    if len(kept) > limit:
        raise too_long
    return kept


# --- access --------------------------------------------------------------------------------------


async def _anchor(
    ctx: AuthContext, kind: str, anchor_id: UUID, locator: Locator | None, action: str
) -> AnchorFacts:
    """The anchor's facts once `action` is allowed on it: 409 for an unknown kind, 404 for a
    missing record, an engagement-less anchor or a client principal."""
    facts = await anchor_facts(ctx, kind, anchor_id, locator)
    if facts is None or ctx.client:
        raise NotFound("anchor")
    if facts.engagement_id is None:
        raise AnchorScopeMismatch  # threads live on an engagement (firm to-dos carry none)
    await authorise(ctx, action, facts.resource())
    return facts


async def _thread(
    ctx: AuthContext, thread_id: UUID, action: str
) -> tuple[CommentThread, AnchorFacts]:
    async with tenant_session(ctx.tenant) as session:
        thread = await repo.get_thread(session, thread_id)
    if thread is None:
        raise NotFound("comment_thread")
    try:
        facts = await _anchor(
            ctx, thread.anchor_kind, thread.anchor_id, thread.anchor_locator, action
        )
    except NotFound:
        raise NotFound("comment_thread") from None
    if facts.engagement_id != thread.engagement_id:
        raise NotFound("comment_thread")  # a provider moved the record: never cross engagements
    return thread, facts


# --- writes --------------------------------------------------------------------------------------


async def _mentions(
    ctx: AuthContext, ref: EngagementRef, ids: Sequence[UUID], team: bool
) -> tuple[list[UUID], bool]:
    """The people this comment mentions, and whether through "@team" (AC-6, AC-7)."""
    allowed = await mentionable(ctx, ref)
    explicit = sorted({u for u in ids if u != ctx.user_id}, key=str)
    if any(u not in allowed for u in explicit):
        raise MentionNotAllowed
    if team:
        return sorted({u for u in allowed if u != ctx.user_id} | set(explicit), key=str), True
    return explicit, False


async def _seal(ctx: AuthContext, body: str) -> tuple[bytes, str]:
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    return await seal(ctx.tenant_id, body.encode(), fingerprint), fingerprint


async def _write_comment(
    tx: UnitOfWork,
    ctx: AuthContext,
    *,
    thread_id: UUID,
    engagement_id: UUID,
    anchor_kind: str,
    anchor_id: UUID,
    sealed: bytes,
    fingerprint: str,
    mentioned: list[UUID],
    via_team: bool,
    corrects: UUID | None,
    citation_ids: Sequence[UUID],
) -> UUID:
    comment = await repo.insert_comment(
        tx.session,
        id=uuid4(),
        tenant_id=ctx.tenant_id,
        engagement_id=engagement_id,
        thread_id=thread_id,
        author_user_id=ctx.user_id,
        author_side="firm",
        body_sealed=sealed,
        body_fingerprint=fingerprint,
        corrects_comment_id=corrects,
        citation_ids=list(citation_ids),
    )
    await repo.insert_mentions(tx.session, ctx.tenant_id, comment.id, mentioned, via_team=via_team)
    await repo.touch_thread(tx.session, thread_id)
    await repo.mark_read(tx.session, ctx.tenant_id, ctx.user_id, thread_id)
    refs: dict[str, UUID | int | str] = {
        "comment_id": comment.id,
        "mentions": len(mentioned),
        "body": fingerprint,
    }
    if corrects is not None:
        refs["corrects"] = corrects
    tx.record(
        "comment.corrected" if corrects is not None else "comment.posted",
        target=Target("comment_thread", thread_id),
        after=Ref(**refs),
    )
    tx.emit(
        CommentCreated(
            comment_id=comment.id,
            thread_id=thread_id,
            anchor_kind=anchor_kind,
            anchor_id=anchor_id,
            engagement_id=engagement_id,
        )
    )
    for user in mentioned:
        tx.emit(
            MentionCreated(
                comment_id=comment.id,
                thread_id=thread_id,
                anchor_kind=anchor_kind,
                anchor_id=anchor_id,
                engagement_id=engagement_id,
                user_id=user,
                mentioned_user_ids=[user],
            )
        )
    return comment.id


async def _shared_text_in_scope(ctx: AuthContext, ref: EngagementRef, body: str) -> None:
    if await check_scope(ctx, ref, body):
        raise CommentOutOfScope


async def open_thread(
    ctx: AuthContext,
    *,
    anchor_kind: str,
    anchor_id: UUID,
    locator: Locator | None,
    body: str,
    mention_user_ids: Sequence[UUID] = (),
    mention_team: bool = False,
    citation_ids: Sequence[UUID] = (),
) -> Posted:
    """AC-1, AC-2, AC-4, AC-6, AC-7: the anchor's thread (opened if it has none) with this first
    comment. A second open on the same anchor and locator posts into the existing thread."""
    facts = await _anchor(ctx, anchor_kind, anchor_id, locator, "comment.create")
    provider = provider_of(anchor_kind)
    key = locator_key(provider, locator)
    pinned = facts.version_no if facts.version_policy == "pin" else None
    text = clean_text(body, MAX_BODY)
    engagement_id = facts.engagement_id
    if engagement_id is None:  # `_anchor` refuses it; kept for the type checker
        raise AnchorScopeMismatch
    ref = await get_ref(ctx, engagement_id)
    mentioned, via_team = await _mentions(ctx, ref, mention_user_ids, mention_team)
    sealed, fingerprint = await _seal(ctx, text)
    async with uow(ctx.tenant) as tx:
        thread = await repo.find_thread(
            tx.session,
            anchor_kind=anchor_kind,
            anchor_id=anchor_id,
            locator_key=key,
            pinned_version_no=pinned,
        )
        if thread is not None and thread.visibility == "shared":
            await _shared_text_in_scope(ctx, ref, text)
        if thread is None:
            thread_id = await repo.insert_thread(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=ref.id,
                work_item_id=facts.work_item_id,
                client_id=ref.client_id,
                anchor_kind=anchor_kind,
                anchor_id=anchor_id,
                anchor_locator=dict(locator) if locator else None,
                anchor_locator_key=key,
                opened_on_version_no=facts.version_no,
                pinned_version_no=pinned,
                created_by=ctx.user_id,
            )
            await repo.insert_event(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=ref.id,
                thread_id=thread_id,
                kind="opened",
                actor_user_id=ctx.user_id,
            )
            tx.record(
                "comment_thread.opened",
                target=Target("comment_thread", thread_id),
                after=Ref(anchor_kind=anchor_kind, anchor_id=anchor_id),
            )
        else:
            thread_id = thread.id
        comment_id = await _write_comment(
            tx,
            ctx,
            thread_id=thread_id,
            engagement_id=ref.id,
            anchor_kind=anchor_kind,
            anchor_id=anchor_id,
            sealed=sealed,
            fingerprint=fingerprint,
            mentioned=mentioned,
            via_team=via_team,
            corrects=None,
            citation_ids=citation_ids,
        )
    return Posted(thread_id, comment_id, mentioned)


async def post_comment(
    ctx: AuthContext,
    thread_id: UUID,
    *,
    body: str,
    mention_user_ids: Sequence[UUID] = (),
    mention_team: bool = False,
    corrects_comment_id: UUID | None = None,
    citation_ids: Sequence[UUID] = (),
) -> Posted:
    """A reply, or the author's Correct… (AC-11): 422 `correction_not_allowed` for anyone else's
    comment, a redacted one, or one in another thread."""
    thread, _facts = await _thread(ctx, thread_id, "comment.create")
    text = clean_text(body, MAX_BODY)
    ref = await get_ref(ctx, thread.engagement_id)
    if corrects_comment_id is not None:
        async with tenant_session(ctx.tenant) as session:
            original = await repo.get_comment(session, corrects_comment_id)
            redacted = (
                await repo.list_comments(session, ctx, [thread_id]) if original is not None else []
            )
        is_redacted = any(c.id == corrects_comment_id and r is not None for c, r in redacted)
        if (
            original is None
            or original.thread_id != thread_id
            or original.author_user_id != ctx.user_id
            or is_redacted
        ):
            raise CorrectionNotAllowed
    if thread.visibility == "shared":
        await _shared_text_in_scope(ctx, ref, text)
    mentioned, via_team = await _mentions(ctx, ref, mention_user_ids, mention_team)
    sealed, fingerprint = await _seal(ctx, text)
    async with uow(ctx.tenant) as tx:
        comment_id = await _write_comment(
            tx,
            ctx,
            thread_id=thread_id,
            engagement_id=thread.engagement_id,
            anchor_kind=thread.anchor_kind,
            anchor_id=thread.anchor_id,
            sealed=sealed,
            fingerprint=fingerprint,
            mentioned=mentioned,
            via_team=via_team,
            corrects=corrects_comment_id,
            citation_ids=citation_ids,
        )
    return Posted(thread_id, comment_id, mentioned)


async def redact(ctx: AuthContext, comment_id: UUID, reason: str) -> UUID:
    """AC-11: a firm administrator with `comment.redact` and a fresh MFA (the matrix); the sealed
    body stays and no route returns it again. Answers the thread."""
    async with tenant_session(ctx.tenant) as session:
        comment = await repo.get_comment(session, comment_id)
    if comment is None or ctx.client:
        raise NotFound("thread_comment")
    ref = await get_ref(ctx, comment.engagement_id)
    await authorise(ctx, "comment.redact", ref.resource())
    why = clean_text(reason, MAX_REASON, too_long=DomainInvalid)
    async with uow(ctx.tenant) as tx:
        made = await repo.insert_redaction(
            tx.session,
            tenant_id=ctx.tenant_id,
            comment_id=comment_id,
            redacted_by=ctx.user_id,
            reason=why,
        )
        if not made:
            raise AlreadyRedacted
        tx.record(
            "comment.redacted",
            target=Target("comment_thread", comment.thread_id),
            after=Ref(comment_id=comment_id),
        )
    return comment.thread_id


async def _move(ctx: AuthContext, thread_id: UUID, *, resolve: bool) -> None:
    thread, _ = await _thread(ctx, thread_id, "comment.resolve")
    expected, status = ("open", "resolved") if resolve else ("resolved", "open")
    async with uow(ctx.tenant) as tx:
        if not await repo.set_thread_status(
            tx.session, thread_id, status=status, expected=expected
        ):
            raise ThreadAlreadyResolved if resolve else ThreadNotResolved
        kind = "resolved" if resolve else "reopened"
        await repo.insert_event(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=thread.engagement_id,
            thread_id=thread_id,
            kind=kind,
            actor_user_id=ctx.user_id,
        )
        tx.record(
            "comment_thread.resolved" if resolve else "comment_thread.reopened",
            target=Target("comment_thread", thread_id),
        )
        event = ThreadResolved if resolve else ThreadReopened
        tx.emit(
            event(
                thread_id=thread_id,
                anchor_kind=thread.anchor_kind,
                anchor_id=thread.anchor_id,
                engagement_id=thread.engagement_id,
            )
        )


async def resolve(ctx: AuthContext, thread_id: UUID) -> None:
    """AC-9: never changes a gate or a sign-off precondition."""
    await _move(ctx, thread_id, resolve=True)


async def reopen(ctx: AuthContext, thread_id: UUID) -> None:
    """AC-10."""
    await _move(ctx, thread_id, resolve=False)


async def mute(ctx: AuthContext, thread_id: UUID, *, muted: bool) -> None:
    """AC-12 (OQ-9): a muted thread adds no unread dot for this person; mentions still notify."""
    thread, _ = await _thread(ctx, thread_id, "comment.read")
    async with uow(ctx.tenant) as tx:
        await repo.set_muted(tx.session, ctx.tenant_id, ctx.user_id, thread_id, muted=muted)
        kind = "muted" if muted else "unmuted"
        await repo.insert_event(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=thread.engagement_id,
            thread_id=thread_id,
            kind=kind,
            actor_user_id=ctx.user_id,
        )
        tx.record(
            "comment_thread.muted" if muted else "comment_thread.unmuted",
            target=Target("comment_thread", thread_id),
        )


async def mark_read(ctx: AuthContext, thread_id: UUID) -> None:
    await _thread(ctx, thread_id, "comment.read")
    async with uow(ctx.tenant) as tx:
        await repo.mark_read(tx.session, ctx.tenant_id, ctx.user_id, thread_id)
        tx.record("comment_thread.read", target=Target("comment_thread", thread_id))


async def share(ctx: AuthContext, thread_id: UUID, *, scope_kind: str, scope_id: UUID) -> None:
    """AC-16: 409 `anchor_not_shareable` on an internal anchor (every one P-05 registers); on a
    client-visible one, the scope must cover it and every firm comment's text must pass the
    engagement's scope check."""
    thread, facts = await _thread(ctx, thread_id, "comment.share")
    if not facts.client_visible:
        raise AnchorNotShareable(facts={"anchor_kind": thread.anchor_kind})
    covers = (scope_kind == "engagement" and scope_id == thread.engagement_id) or (
        scope_kind == "work_item"
        and thread.work_item_id is not None
        and scope_id == thread.work_item_id
    )
    if not covers:
        raise ShareScopeInvalid
    ref = await get_ref(ctx, thread.engagement_id)
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.list_comments(session, ctx, [thread_id])
    for comment, redaction in rows:
        if redaction is None and comment.author_side == "firm":
            text = await open_sealed(ctx.tenant_id, comment.body_sealed, comment.body_fingerprint)
            await _shared_text_in_scope(ctx, ref, text.decode())
    async with uow(ctx.tenant) as tx:
        if await repo.share_thread(
            tx.session, thread_id, scope_kind=scope_kind, scope_id=scope_id
        ):
            await repo.insert_event(
                tx.session,
                tenant_id=ctx.tenant_id,
                engagement_id=thread.engagement_id,
                thread_id=thread_id,
                kind="shared",
                actor_user_id=ctx.user_id,
            )
            tx.record(
                "comment_thread.shared",
                target=Target("comment_thread", thread_id),
                after=Ref(scope_kind=scope_kind, scope_id=scope_id),
            )


# --- reads ---------------------------------------------------------------------------------------


async def _views(
    ctx: AuthContext, threads: Sequence[CommentThread], facts: AnchorFacts
) -> list[ThreadView]:
    if not threads:
        return []
    ids = [t.id for t in threads]
    async with tenant_session(ctx.tenant) as session:
        rows = await repo.list_comments(session, ctx, ids)
        mentions = await repo.list_mentions(session, ctx, [c.id for c, _ in rows])
        events = await repo.list_events(session, ctx, ids)
        reads = {r.thread_id: r for r in await repo.list_reads(session, ctx, ids)}
    by_comment: dict[UUID, list[UUID]] = {}
    for m in mentions:
        by_comment.setdefault(m.comment_id, []).append(m.user_id)
    corrected: dict[UUID, UUID] = {}
    for c, _ in rows:
        if c.corrects_comment_id is not None:
            corrected.setdefault(c.corrects_comment_id, c.id)
    comments: dict[UUID, list[CommentView]] = {}
    for c, r in rows:
        body = None
        if r is None:
            body = (await open_sealed(ctx.tenant_id, c.body_sealed, c.body_fingerprint)).decode()
        comments.setdefault(c.thread_id, []).append(
            CommentView(
                c.id,
                c.author_user_id,
                c.author_side,
                body,
                c.corrects_comment_id,
                corrected.get(c.id),
                sorted(by_comment.get(c.id, []), key=str),
                list(c.citation_ids or []),
                None if r is None else RedactionView(r.redacted_by, r.created_at, r.reason),
                c.created_at,
            )
        )
    by_thread: dict[UUID, list[EventView]] = {}
    for e in events:
        by_thread.setdefault(e.thread_id, []).append(
            EventView(e.kind, e.actor_user_id, e.ref_type, e.ref_id, e.created_at)
        )
    allowed = await allowed_actions(ctx, facts.resource(), THREAD_ACTIONS)
    views: list[ThreadView] = []
    for t in threads:
        read = reads.get(t.id)
        muted = read is not None and read.muted_at is not None
        last_read = read.last_read_at if read is not None else None
        unread = (
            not muted
            and t.last_comment_at is not None
            and (last_read is None or t.last_comment_at > last_read)
        )
        actions = [
            a
            for a in THREAD_ACTIONS
            if a in allowed
            and not (
                a == "comment.share" and (not facts.client_visible or t.visibility != "internal")
            )
        ]
        views.append(
            ThreadView(
                t.id,
                t.anchor_kind,
                t.anchor_id,
                t.anchor_locator,
                facts,
                t.engagement_id,
                t.status,
                t.visibility,
                t.opened_on_version_no,
                t.pinned_version_no,
                t.last_comment_at,
                comments.get(t.id, []),
                by_thread.get(t.id, []),
                unread,
                muted,
                actions,
            )
        )
    return views


async def threads_on(
    ctx: AuthContext,
    *,
    anchor_kind: str,
    anchor_id: UUID,
    locator: Locator | None,
    status: str | None,
) -> tuple[list[ThreadView], dict[str, int]]:
    """AC-1, AC-3, AC-9: the anchor's threads with their comments, and the Open/Resolved counts
    for the anchor (before the status filter)."""
    facts = await _anchor(ctx, anchor_kind, anchor_id, locator, "comment.read")
    key = locator_key(provider_of(anchor_kind), locator) if locator else None
    async with tenant_session(ctx.tenant) as session:
        threads = await repo.list_threads_on(
            session, ctx, anchor_kind=anchor_kind, anchor_id=anchor_id, locator_key=key
        )
    counts = {
        "open": sum(t.status == "open" for t in threads),
        "resolved": sum(t.status == "resolved" for t in threads),
    }
    if status is not None:
        threads = [t for t in threads if t.status == status]
    return await _views(ctx, threads, facts), counts


async def thread(ctx: AuthContext, thread_id: UUID) -> ThreadView:
    found, facts = await _thread(ctx, thread_id, "comment.read")
    return (await _views(ctx, [found], facts))[0]


async def counts(
    ctx: AuthContext, anchors: Sequence[tuple[str, UUID, Locator | None]]
) -> list[AnchorCount]:
    """The C-27 chips: per anchor, open and resolved threads and the reader's unread ones. An
    anchor the reader may not read counts nothing (no error that would tell it apart)."""
    readable: list[tuple[str, UUID, Locator | None]] = []
    for kind, anchor_id, locator in anchors:
        try:
            await _anchor(ctx, kind, anchor_id, locator, "comment.read")
        except (NotFound, Forbidden, AnchorScopeMismatch):
            continue
        readable.append((kind, anchor_id, locator))
    async with tenant_session(ctx.tenant) as session:
        threads = await repo.list_threads_on_anchors(
            session, ctx, sorted({(k, a) for k, a, _ in readable}, key=str)
        )
        reads = {
            r.thread_id: r for r in await repo.list_reads(session, ctx, [t.id for t in threads])
        }
    found: list[AnchorCount] = []
    for kind, anchor_id, locator in anchors:
        key = locator_key(provider_of(kind), locator) if locator else None
        mine = [
            t
            for t in threads
            if (kind, anchor_id) in {(k, a) for k, a, _ in readable}
            and t.anchor_kind == kind
            and t.anchor_id == anchor_id
            and (key is None or t.anchor_locator_key == key)
        ]
        unread = 0
        for t in mine:
            read = reads.get(t.id)
            if read is not None and read.muted_at is not None:
                continue
            last = read.last_read_at if read is not None else None
            if t.last_comment_at is not None and (last is None or t.last_comment_at > last):
                unread += 1
        found.append(
            AnchorCount(
                kind,
                anchor_id,
                dict(locator) if locator else None,
                sum(t.status == "open" for t in mine),
                sum(t.status == "resolved" for t in mine),
                unread,
            )
        )
    return found
