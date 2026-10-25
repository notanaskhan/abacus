"""Comments on request items and their evidence versions (SPEC-032; TASK-062; ADR-109).

Append-only: nothing is edited or deleted; an author corrects with a new comment, and a firm
administrator may redact one posted in error. Pinned: each item and each of its versions has its
own thread. A firm member's comment is internal unless shared (after the outbound scope check,
Q4); a client's is always shared, and client roles never receive an internal note. The text is
Restricted: sealed per tenant (`kernel.crypto`), never logged, never in an audit reference.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID, uuid4

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import EngagementRef, get_ref
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    client_admins,
    engagement_role_of,
    names_of,
    team_of,
)
from abacus.modules.requests.events import CommentMentioned
from abacus.modules.requests.repository import (
    fulfilling_versions,
    get_comment,
    insert_comment,
    insert_mentions,
    insert_redaction,
    list_mentions,
    list_thread,
    mark_thread_read,
    redaction_of,
)
from abacus.modules.requests.service import RequestItemRef, read_item

MAX_BODY: Final = 4000
MAX_REASON: Final = 500
CLIENT_ROLES: Final = frozenset({"client_admin", "client_contributor"})

# Violation kinds of the text, or an empty list (communications registers it, TASK-062 D1).
ScopeCheck = Callable[[AuthContext, EngagementRef, str], Awaitable[Sequence[str]]]
_scope_check: ScopeCheck | None = None


def register_comment_scope_check(check: ScopeCheck) -> None:
    global _scope_check
    if _scope_check is not None and _scope_check is not check:
        raise RuntimeError("the comment scope check is already registered")
    _scope_check = check


def scope_check() -> ScopeCheck | None:
    """The registered client-text scope check (`communications`), for the request send too."""
    return _scope_check


class CommentOutOfScope(DomainConflict):
    """AC-7: the comment names something outside the engagement; it wasn't posted."""

    code = "out_of_scope"


class SharingUnavailable(DomainConflict):
    """No scope check is registered, so nothing a firm member writes can be shared (D1)."""

    code = "sharing_unavailable"


class MentionNotAllowed(DomainInvalid):
    code = "mention_not_allowed"


class CorrectionNotAllowed(DomainInvalid):
    code = "correction_not_allowed"


class EmptyComment(DomainInvalid):
    code = "empty_comment"


class AlreadyRedacted(DomainConflict):
    code = "already_redacted"


@dataclass(frozen=True)
class RedactionView:
    redacted_by_name: str
    redacted_at: datetime
    reason: str


@dataclass(frozen=True)
class CommentView:
    id: UUID
    request_item_id: UUID
    evidence_version_id: UUID | None
    author_user_id: UUID
    author_name: str
    author_side: str
    visibility: str
    text: str | None  # None once redacted
    created_at: datetime
    corrects: UUID | None
    corrected_by: list[UUID]
    mentions: list[UUID]
    redaction: RedactionView | None


@dataclass(frozen=True)
class MentionCandidate:
    user_id: UUID
    display_name: str
    side: str


def clean_text(text: str, limit: int) -> str:
    """Plain text: control characters other than line breaks and tabs removed, trimmed."""
    kept = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C").strip()
    if not kept:
        raise EmptyComment
    if len(kept) > limit:
        raise DomainInvalid("too long")
    return kept


async def insert_ignore_note(
    tx: UnitOfWork, ctx: AuthContext, engagement_id: UUID, item_id: UUID, body: str
) -> UUID:
    """R-01-T08: a client's note on their Ignore, in the Ignore's unit of work (which authorised
    `request_item.ignore`): a shared client comment on the request with origin `ignore_note`,
    sealed like every comment. The caller audits it (`request_item.ignore_note_added`)."""
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    sealed = await seal(ctx.tenant_id, body.encode(), fingerprint)
    comment_id = uuid4()
    await insert_comment(
        tx.session,
        id=comment_id,
        tenant_id=ctx.tenant_id,
        engagement_id=engagement_id,
        request_item_id=item_id,
        evidence_version_id=None,
        author_user_id=ctx.user_id,
        author_side="client",
        visibility="shared",
        body_sealed=sealed,
        body_fingerprint=fingerprint,
        origin="ignore_note",
    )
    return comment_id


async def check_return_comment(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, body: str
) -> None:
    """TASK-1252: a screening return's sender will post its shared comment, so they must be
    allowed `comment.share` on the request (checked at the send, in their own request), and the
    body must be a comment's (`clean_text`: not empty, at most 4000 characters, 422)."""
    ref = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, "comment.share", _resource(ref, item))
    clean_text(body, MAX_BODY)


async def insert_return_comment(
    tx: UnitOfWork,
    tenant_id: UUID,
    engagement_id: UUID,
    item_id: UUID,
    *,
    comment_id: UUID,
    author_user_id: UUID,
    body: str,
) -> bool:
    """TASK-1252: a screening return's shared comment, the body its sender sent, posted when the
    follow-up is delivered (after the Undo window). Its sender was authorised `comment.share` at
    the send and its text scope-checked there. One per follow-up: the caller derives
    `comment_id` from it, so a redelivery writes nothing (False). The caller audits it."""
    if await get_comment(tx.session, comment_id) is not None:
        return False
    text = clean_text(body, MAX_BODY)  # as checked at the send
    fingerprint = hashlib.sha256(text.encode()).hexdigest()
    sealed = await seal(tenant_id, text.encode(), fingerprint)
    await insert_comment(
        tx.session,
        id=comment_id,
        tenant_id=tenant_id,
        engagement_id=engagement_id,
        request_item_id=item_id,
        evidence_version_id=None,
        author_user_id=author_user_id,
        author_side="firm",
        visibility="shared",
        body_sealed=sealed,
        body_fingerprint=fingerprint,
    )
    return True


def _resource(ref: EngagementRef, item: RequestItemRef) -> Resource:
    return Resource.engagement(
        ref.tenant_id, ref.id, archived=ref.archived, client_id=ref.client_id, item=item.facts
    )


async def _thread(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID | None, action: str
) -> tuple[EngagementRef, RequestItemRef, str | None]:
    """The engagement, the item and the caller's role, once `action` is allowed on the item with
    its client facts; NotFound for a version that doesn't fulfil the item."""
    ref = await get_ref(ctx, engagement_id)
    item = await read_item(ctx.tenant, engagement_id, item_id)
    await authorise(ctx, action, _resource(ref, item))
    if version_id is not None:
        async with tenant_session(ctx.tenant) as session:
            if version_id not in await fulfilling_versions(session, item_id):
                raise NotFound("evidence_version")
    return ref, item, await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)


async def candidates(
    ctx: AuthContext, engagement_id: UUID, item: RequestItemRef, visibility: str
) -> dict[UUID, str]:
    """D3: who may be mentioned (and so read the comment), with their side: the engagement's
    firm team; on a shared comment, also the item's client readers (SPEC-020: client admins on a
    client-visible item, and its assigned contributor)."""
    found: dict[UUID, str] = {u: "firm" for u, _ in await team_of(ctx.tenant_id, engagement_id)}
    if visibility == "shared" and item.client_visible:
        for admin in await client_admins(ctx.tenant, engagement_id):
            found[admin] = "client"
        assignee = item.client_assignee_user_id
        if (
            assignee is not None
            and await engagement_role_of(ctx.tenant, engagement_id, assignee)
            == "client_contributor"
        ):
            found[assignee] = "client"
    return found


async def mention_candidates(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, visibility: str
) -> list[MentionCandidate]:
    _, item, role = await _thread(ctx, engagement_id, item_id, None, "comment.create")
    if role in CLIENT_ROLES:
        visibility = "shared"
    found = await candidates(ctx, engagement_id, item, visibility)
    found.pop(ctx.user_id, None)
    names = await names_of(sorted(found, key=str))
    return sorted(
        (MentionCandidate(u, names.get(u, ""), side) for u, side in found.items()),
        key=lambda c: (c.side, c.display_name.casefold()),
    )


async def post_comment(
    ctx: AuthContext,
    engagement_id: UUID,
    item_id: UUID,
    version_id: UUID | None,
    *,
    text: str,
    share: bool = False,
    corrects: UUID | None = None,
    mentions: Sequence[UUID] = (),
) -> CommentView:
    """AC-1, AC-2, AC-4, AC-5, AC-7."""
    ref, item, role = await _thread(ctx, engagement_id, item_id, version_id, "comment.create")
    body = clean_text(text, MAX_BODY)
    client = role in CLIENT_ROLES
    visibility = "shared" if client or share else "internal"
    if corrects is not None:
        async with tenant_session(ctx.tenant) as session:
            original = await get_comment(session, corrects)
            redacted = await redaction_of(session, corrects) is not None
        if (
            original is None
            or original.request_item_id != item_id
            or original.evidence_version_id != version_id
            or original.author_user_id != ctx.user_id
            or redacted
        ):
            raise CorrectionNotAllowed
        visibility = original.visibility  # a correction is read by whoever read the original
    if visibility == "shared" and not client:
        await authorise(ctx, "comment.share", _resource(ref, item))
        if _scope_check is None:
            raise SharingUnavailable
        if await _scope_check(ctx, ref, body):
            raise CommentOutOfScope
    allowed = await candidates(ctx, engagement_id, item, visibility)
    mentioned = sorted({u for u in mentions if u != ctx.user_id}, key=str)
    if any(u not in allowed for u in mentioned):
        raise MentionNotAllowed
    fingerprint = hashlib.sha256(body.encode()).hexdigest()
    sealed = await seal(ctx.tenant_id, body.encode(), fingerprint)
    comment_id = uuid4()
    async with uow(ctx.tenant) as tx:
        row = await insert_comment(
            tx.session,
            id=comment_id,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_item_id=item_id,
            evidence_version_id=version_id,
            author_user_id=ctx.user_id,
            author_side="client" if client else "firm",
            visibility=visibility,
            body_sealed=sealed,
            body_fingerprint=fingerprint,
            corrects_comment_id=corrects,
        )
        await insert_mentions(tx.session, ctx.tenant_id, comment_id, mentioned)
        refs: dict[str, UUID | int | str] = {
            "request_item_id": item_id,
            "shared": int(visibility == "shared"),
            "mentions": len(mentioned),
            "body": fingerprint,
        }
        if version_id is not None:
            refs["evidence_version_id"] = version_id
        if corrects is not None:
            refs["corrects"] = corrects
        tx.record("comment.posted", target=Target("comment", comment_id), after=Ref(**refs))
        if mentioned:
            tx.emit(
                CommentMentioned(
                    comment_id=comment_id,
                    request_item_id=item_id,
                    engagement_id=engagement_id,
                    mentioned_user_ids=list(mentioned),
                )
            )
    names = await names_of([ctx.user_id])
    return CommentView(
        row.id,
        item_id,
        version_id,
        ctx.user_id,
        names.get(ctx.user_id, ""),
        row.author_side,
        visibility,
        body,
        row.created_at,
        corrects,
        [],
        mentioned,
        None,
    )


async def thread(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID | None
) -> list[CommentView]:
    """AC-1, AC-3, AC-6: the thread, oldest first; client roles get shared comments only, and a
    redacted comment's text is never returned."""
    _, _, role = await _thread(ctx, engagement_id, item_id, version_id, "comment.read")
    async with tenant_session(ctx.tenant) as session:
        rows = await list_thread(
            session, ctx, item_id, version_id, shared_only=role in CLIENT_ROLES
        )
        mentions = await list_mentions(session, ctx, [c.id for c, _ in rows])
    people = {c.author_user_id for c, _ in rows} | {r.redacted_by for _, r in rows if r}
    names = await names_of(sorted(people, key=str))
    corrected: dict[UUID, list[UUID]] = {}
    for c, _ in rows:
        if c.corrects_comment_id is not None:
            corrected.setdefault(c.corrects_comment_id, []).append(c.id)
    views: list[CommentView] = []
    for c, redaction in rows:
        text = None
        if redaction is None:
            text = (await open_sealed(ctx.tenant_id, c.body_sealed, c.body_fingerprint)).decode()
        views.append(
            CommentView(
                c.id,
                c.request_item_id,
                c.evidence_version_id,
                c.author_user_id,
                names.get(c.author_user_id, ""),
                c.author_side,
                c.visibility,
                text,
                c.created_at,
                c.corrects_comment_id,
                corrected.get(c.id, []),
                mentions.get(c.id, []),
                None
                if redaction is None
                else RedactionView(
                    names.get(redaction.redacted_by, ""), redaction.created_at, redaction.reason
                ),
            )
        )
    return views


async def mark_read(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, version_id: UUID | None
) -> None:
    """Q6: the caller has read this thread up to now."""
    await _thread(ctx, engagement_id, item_id, version_id, "comment.read")
    async with uow(ctx.tenant) as tx:
        await mark_thread_read(tx.session, ctx.tenant_id, ctx.user_id, item_id, version_id)
        refs: dict[str, UUID | int | str] = {"request_item_id": item_id}
        if version_id is not None:
            refs["evidence_version_id"] = version_id
        tx.record("comment_thread.read", target=Target("request_item", item_id), after=Ref(**refs))


async def redact(
    ctx: AuthContext, engagement_id: UUID, item_id: UUID, comment_id: UUID, reason: str
) -> None:
    """AC-6: a firm administrator hides a comment posted in error; the sealed text stays, and no
    route returns it again (SPEC-032 Q5)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "comment.redact", ref.resource())
    why = clean_text(reason, MAX_REASON)
    async with uow(ctx.tenant) as tx:
        comment = await get_comment(tx.session, comment_id)
        if (
            comment is None
            or comment.engagement_id != engagement_id
            or comment.request_item_id != item_id
        ):
            raise NotFound("comment")
        made = await insert_redaction(
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
            target=Target("comment", comment_id),
            after=Ref(request_item_id=comment.request_item_id),
        )
