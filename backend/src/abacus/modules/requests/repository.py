"""Requests data access: request lists and request items only (ADR-008, ADR-103)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import Select, Subquery, and_, func, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from abacus.kernel.errors import DomainConflict
from abacus.kernel.listing import Position, capped_total, keyset, status_counts
from abacus.modules.identity.api import AuthContext, visible, visible_items
from abacus.modules.requests.guidance import Guidance
from abacus.modules.requests.models import (
    BinderActivity,
    BinderRecipient,
    ClientItemResponse,
    ClientListDone,
    Comment,
    CommentMention,
    CommentRead,
    CommentRedaction,
    Fulfilment,
    FulfilmentWithdrawal,
    RequestCategory,
    RequestItem,
    RequestList,
)


class NoWorkItem(DomainConflict):
    """A request needs a binder, and a binder a work item: the engagement has none yet."""

    code = "no_work_item"


async def request_list_for(
    session: AsyncSession, tenant_id: UUID, engagement_id: UUID
) -> tuple[UUID, bool]:
    """The engagement's first PBC binder and whether this call created it (TASK-008 Q5). Concurrent
    first items both end up with the same binder (one per work item, kind and part, enforced by
    the database; the work item is the engagement's assurance item, filled by the database)."""
    first = (
        RequestList.engagement_id == engagement_id,
        RequestList.kind == "pbc",
        RequestList.part == 1,
    )
    existing = (await session.execute(select(RequestList.id).where(*first))).scalar_one_or_none()
    if existing is not None:
        return existing, False
    try:
        created = (
            await session.execute(
                pg_insert(RequestList)
                # Published at once: the publish flow (BND-01) isn't built yet.
                .values(
                    id=uuid4(),
                    tenant_id=tenant_id,
                    engagement_id=engagement_id,
                    status="published",
                )
                .on_conflict_do_nothing(constraint="request_lists_binder_key")
                .returning(RequestList.id)
            )
        ).scalar_one_or_none()
    except IntegrityError as exc:
        # 0070's trigger: a binder belongs to a work item, and the engagement has none yet.
        if getattr(exc.orig, "sqlstate", None) == "23503":
            raise NoWorkItem("request_list") from None
        raise
    if created is not None:
        return created, True
    winner = (await session.execute(select(RequestList.id).where(*first))).scalar_one()
    return winner, False


async def insert_request_item(
    session: AsyncSession,
    *,
    item_id: UUID,
    tenant_id: UUID,
    engagement_id: UUID,
    request_list_id: UUID,
    description: str,
    audit_area: str,
    created_by: UUID,
    retrievability_tier: str | None = None,
    dataset: str | None = None,
    tier_source: str | None = None,
    tier_rule: str | None = None,
    document_kind: str | None = None,
    document_kind_source: str | None = None,
    guidance: Guidance | None = None,
    binder_fields: Mapping[str, object] | None = None,
) -> RequestItem:
    """`binder_fields`: P-06-T05's request fields (title, category, kind, source tag), when set."""
    g = guidance or Guidance()
    return (
        await session.execute(
            insert(RequestItem)
            .values(
                id=item_id,
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                request_list_id=request_list_id,
                description=description,
                audit_area=audit_area,
                created_by=created_by,
                retrievability_tier=retrievability_tier,
                dataset=dataset,
                tier_source=tier_source,
                tier_rule=tier_rule,
                document_kind=document_kind,
                document_kind_source=document_kind_source,
                why=g.why,
                good_looks_like=g.good_looks_like,
                blocks_fieldwork=g.blocks_fieldwork,
                effort=g.effort,
                guidance_source=g.source,
                guidance_approved_by=g.approved_by,
                **dict(binder_fields or {}),
            )
            .returning(RequestItem)
        )
    ).scalar_one()


async def list_request_items(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[tuple[RequestItem, UUID | None]]:
    """Each visible item of the engagement with the evidence version that last fulfilled it."""
    latest = (
        select(Fulfilment.evidence_version_id)
        .where(Fulfilment.request_item_id == RequestItem.id, live_fulfilment())
        .order_by(Fulfilment.created_at.desc(), Fulfilment.id.desc())
        .limit(1)
        .correlate(RequestItem)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(RequestItem, latest)
        .where(
            RequestItem.engagement_id == engagement_id,
            visible_items(
                ctx,
                "request_item.read",
                RequestItem.engagement_id,
                RequestItem.client_visible,
                RequestItem.client_assignee_user_id,
            ),
        )
        .order_by(RequestItem.created_at, RequestItem.id)
    )
    return [(item, version_id) for item, version_id in rows.all()]


async def items_to_roll_forward(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID, limit: int = 2000
) -> Sequence[RequestItem]:
    """Last year's items, for a roll-forward proposal or copy (SPEC-025 AC-2; TASK-048)."""
    return (
        (
            await session.execute(
                select(RequestItem)
                .where(
                    visible(ctx, "roll_forward.read", RequestItem.engagement_id),
                    RequestItem.engagement_id == engagement_id,
                )
                .order_by(RequestItem.created_at, RequestItem.id)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def set_client_fields(
    session: AsyncSession,
    item_id: UUID,
    *,
    client_visible: bool | None = None,
    client_assignee: UUID | Literal["unchanged"] | None = "unchanged",
) -> None:
    """Change the item's client facts (SPEC-020); the caller holds the item's lock."""
    values: dict[str, object] = {}
    if client_visible is not None:
        values["client_visible"] = client_visible
    if client_assignee != "unchanged":
        values["client_assignee_user_id"] = client_assignee
    if values:
        await session.execute(
            update(RequestItem).where(RequestItem.id == item_id).values(**values)
        )


def live_fulfilment() -> ColumnElement[bool]:
    """A fulfilment whose version the client has not withdrawn (P-06-T19; ADR-162 §4): every
    read of fulfilments applies it, so a withdrawn upload is as if it never arrived."""
    return ~(
        select(FulfilmentWithdrawal.fulfilment_id)
        .where(FulfilmentWithdrawal.fulfilment_id == Fulfilment.id)
        .exists()
    )


async def fulfilling_versions(session: AsyncSession, item_id: UUID) -> Sequence[UUID]:
    """Every version that fulfils the item, oldest first, for a caller that authorised on the
    item (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(Fulfilment.evidence_version_id)
                .where(Fulfilment.request_item_id == item_id, live_fulfilment())
                .order_by(Fulfilment.created_at, Fulfilment.id)
            )
        )
        .scalars()
        .all()
    )


async def get_request_item(
    session: AsyncSession, item_id: UUID, *, lock: bool = False
) -> RequestItem | None:
    """The item; `lock` holds its row until the transaction ends, so a review decision and a new
    fulfilment of the same item never interleave (TASK-019 security review H3)."""
    query = select(RequestItem).where(RequestItem.id == item_id)
    if lock:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def insert_fulfilment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    request_item_id: UUID,
    evidence_version_id: UUID,
    created_by_kind: str,
    created_by_id: str,
) -> UUID | None:
    """The new fulfilment's ID, or None if this version already fulfils this item."""
    return (
        await session.execute(
            pg_insert(Fulfilment)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                request_item_id=request_item_id,
                evidence_version_id=evidence_version_id,
                created_by_kind=created_by_kind,
                created_by_id=created_by_id,
            )
            .on_conflict_do_nothing(constraint="fulfilments_once")
            .returning(Fulfilment.id)
        )
    ).scalar_one_or_none()


async def upload_link(
    session: AsyncSession, evidence_version_id: UUID, uploader: str
) -> UUID | None:
    """The item an upload was made to: the version's earliest live fulfilment its uploader made
    by hand (`fulfil_by_upload`), for a caller that authorised on the version."""
    return (
        await session.execute(
            select(Fulfilment.request_item_id)
            .where(
                Fulfilment.evidence_version_id == evidence_version_id,
                Fulfilment.created_by_kind == "human",
                Fulfilment.created_by_id == uploader,
                live_fulfilment(),
            )
            .order_by(Fulfilment.created_at, Fulfilment.id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def void_fulfilments(
    session: AsyncSession,
    *,
    evidence_version_id: UUID,
    withdrawn_by: UUID,
    item_ids: Sequence[UUID],
) -> list[tuple[UUID, UUID]]:
    """P-06-T19: record every live fulfilment of the withdrawn version as voided; returns
    (fulfilment, item) pairs, for a caller that authorised `evidence.withdraw` on the version
    (LIST_EXEMPT: one version's own links)."""
    rows = (
        await session.execute(
            select(Fulfilment).where(
                Fulfilment.evidence_version_id == evidence_version_id,
                Fulfilment.request_item_id.in_(list(item_ids)),
                live_fulfilment(),
            )
        )
    ).scalars()
    voided: list[tuple[UUID, UUID]] = []
    for row in rows.all():
        await session.execute(
            insert(FulfilmentWithdrawal).values(
                tenant_id=row.tenant_id,
                fulfilment_id=row.id,
                engagement_id=row.engagement_id,
                request_item_id=row.request_item_id,
                evidence_version_id=row.evidence_version_id,
                withdrawn_by_user_id=withdrawn_by,
            )
        )
        voided.append((row.id, row.request_item_id))
    return voided


async def revert_to_requested(session: AsyncSession, item_id: UUID) -> bool:
    """P-06-T19 (SPEC-319 §6): an `uploaded` item left with no live fulfilment goes back to
    `requested`; False when it still holds one, or was not `uploaded`."""
    still = (
        select(Fulfilment.id)
        .where(Fulfilment.request_item_id == item_id, live_fulfilment())
        .exists()
    )
    result = await session.execute(
        update(RequestItem)
        .where(RequestItem.id == item_id, RequestItem.status == "uploaded", ~still)
        .values(status="requested")
        .returning(RequestItem.id)
    )
    return result.scalar_one_or_none() is not None


async def mark_received(session: AsyncSession, item_id: UUID) -> bool:
    """`open` or `needs_revision` → `received`; False if the item was neither (already received or
    further on). A sent-back item takes new evidence (SPEC-004, TASK-019)."""
    result = await session.execute(
        update(RequestItem)
        .where(
            RequestItem.id == item_id, RequestItem.status.in_(("draft", "requested", "returned"))
        )
        .values(status="uploaded")
        .returning(RequestItem.id)
    )
    return result.scalar_one_or_none() is not None


async def newest_fulfilment(session: AsyncSession, item_id: UUID) -> UUID | None:
    """The version that last fulfilled the item (newest fulfilment first, then its id)."""
    return (
        await session.execute(
            select(Fulfilment.evidence_version_id)
            .where(Fulfilment.request_item_id == item_id, live_fulfilment())
            .order_by(Fulfilment.created_at.desc(), Fulfilment.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def list_fulfilled_versions(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[tuple[RequestItem, UUID, datetime, UUID]]:
    """Every (item, version, fulfilled at) of the engagement the actor may review (SPEC-004)."""
    rows = await session.execute(
        select(RequestItem, Fulfilment.evidence_version_id, Fulfilment.created_at, Fulfilment.id)
        .join(Fulfilment, Fulfilment.request_item_id == RequestItem.id)
        .where(
            RequestItem.engagement_id == engagement_id,
            visible(ctx, "review.read", RequestItem.engagement_id),
            live_fulfilment(),
        )
        .order_by(RequestItem.created_at, RequestItem.id, Fulfilment.created_at, Fulfilment.id)
    )
    return [(item, version_id, at, fid) for item, version_id, at, fid in rows.all()]


async def set_status(
    session: AsyncSession, item_id: UUID, *, allowed_from: tuple[str, ...], to: str
) -> bool:
    """Move the item to `to` if it is in one of `allowed_from`; False otherwise."""
    result = await session.execute(
        update(RequestItem)
        .where(RequestItem.id == item_id, RequestItem.status.in_(allowed_from))
        .values(status=to)
        .returning(RequestItem.id)
    )
    return result.scalar_one_or_none() is not None


async def items_fulfilled_by(
    session: AsyncSession, evidence_version_id: UUID
) -> Sequence[RequestItem]:
    """Items a version fulfils, for a caller that authorised on the version's engagement
    (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(RequestItem)
                .join(Fulfilment, Fulfilment.request_item_id == RequestItem.id)
                .where(Fulfilment.evidence_version_id == evidence_version_id, live_fulfilment())
                .order_by(RequestItem.created_at, RequestItem.id)
            )
        )
        .scalars()
        .all()
    )


async def item_keys(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[tuple[str, str]]:
    """(audit area, description) of the engagement's items, for de-duplication (SPEC-018 Q3)."""
    rows = await session.execute(
        select(RequestItem.audit_area, RequestItem.description).where(
            RequestItem.engagement_id == engagement_id,
            visible(ctx, "request_item.read", RequestItem.engagement_id),
        )
    )
    return [(area, description) for area, description in rows.all()]


async def set_classification(
    session: AsyncSession,
    item_id: UUID,
    *,
    tier: str | None,
    dataset: str | None,
    source: str | None,
    rule: str | None,
) -> None:
    await session.execute(
        update(RequestItem)
        .where(RequestItem.id == item_id)
        .values(retrievability_tier=tier, dataset=dataset, tier_source=source, tier_rule=rule)
    )


async def set_document_kind(
    session: AsyncSession, item_id: UUID, *, kind: str | None, source: str | None
) -> None:
    """SPEC-029 (TASK-055): the document the item expects, and whether a rule or the team set
    it."""
    await session.execute(
        update(RequestItem)
        .where(RequestItem.id == item_id)
        .values(document_kind=kind, document_kind_source=source)
    )


async def set_guidance(
    session: AsyncSession,
    item_id: UUID,
    guidance: Guidance,
    *,
    still_needed: str | None = None,
    approved_by: UUID | None = None,
) -> None:
    """SPEC-031 (TASK-060): the guidance; `still_needed` only changes when the firm edits."""
    values: dict[str, object] = {
        "why": guidance.why,
        "good_looks_like": guidance.good_looks_like,
        "blocks_fieldwork": guidance.blocks_fieldwork,
        "effort": guidance.effort,
        "guidance_source": guidance.source,
        "guidance_approved_by": approved_by,  # SPEC-035: drafted guidance only
    }
    if guidance.source == "firm":
        values["still_needed"] = still_needed
    await session.execute(update(RequestItem).where(RequestItem.id == item_id).values(**values))


# --- Due dates (SPEC-027; TASK-051) ------------------------------------------------------------


async def set_due_dates(
    session: AsyncSession, engagement_id: UUID, item_ids: Sequence[UUID], due_on: date | None
) -> int:
    found = await session.execute(
        update(RequestItem)
        .where(RequestItem.engagement_id == engagement_id, RequestItem.id.in_(item_ids))
        .values(due_on=due_on)
        .returning(RequestItem.id)
    )
    return len(found.all())


async def default_due_on(session: AsyncSession, engagement_id: UUID) -> date | None:
    return await session.scalar(
        select(RequestList.default_due_on).where(
            RequestList.engagement_id == engagement_id,
            RequestList.kind == "pbc",
            RequestList.part == 1,
        )
    )


async def set_default_due_on(
    session: AsyncSession, tenant_id: UUID, engagement_id: UUID, due_on: date | None
) -> UUID:
    list_id, _ = await request_list_for(session, tenant_id, engagement_id)
    await session.execute(
        update(RequestList).where(RequestList.id == list_id).values(default_due_on=due_on)
    )
    return list_id


async def overdue_items(
    session: AsyncSession, engagement_id: UUID, today: date
) -> Sequence[tuple[RequestItem, date]]:
    """Open or sent-back items past their due date (their own, else the list's), for the
    engagement agent's reminders (LIST_EXEMPT: the platform, not a person, reads them)."""
    due = func.coalesce(RequestItem.due_on, RequestList.default_due_on)
    rows = await session.execute(
        select(RequestItem, due)
        .join(RequestList, RequestList.id == RequestItem.request_list_id)
        .where(
            RequestItem.engagement_id == engagement_id,
            RequestItem.status.in_(("requested", "returned")),
            due < today,
        )
        .order_by(due, RequestItem.created_at, RequestItem.id)
    )
    return [(item, d) for item, d in rows.all()]


async def overdue_counts(
    session: AsyncSession, ctx: AuthContext, engagement_ids: Sequence[UUID], today: date
) -> dict[UUID, int]:
    """TASK-102: per engagement, open or sent-back items past due, in one query, through
    `visible()` (walls and independence apply)."""
    if not engagement_ids:
        return {}
    due = func.coalesce(RequestItem.due_on, RequestList.default_due_on)
    rows = await session.execute(
        select(RequestItem.engagement_id, func.count())
        .join(RequestList, RequestList.id == RequestItem.request_list_id)
        .where(
            RequestItem.engagement_id.in_(engagement_ids),
            RequestItem.status.in_(("requested", "returned")),
            due < today,
            visible(ctx, "request_item.read", RequestItem.engagement_id),
        )
        .group_by(RequestItem.engagement_id)
    )
    return {e: int(n) for e, n in rows.all()}


# --- Comments (SPEC-032; TASK-062; ADR-109) ------------------------------------------------------


def _thread(item_id: UUID, version_id: UUID | None) -> ColumnElement[bool]:
    return and_(
        Comment.request_item_id == item_id,
        Comment.evidence_version_id.is_not_distinct_from(version_id),
    )


async def insert_comment(session: AsyncSession, **values: object) -> Comment:
    return (
        await session.execute(insert(Comment).values(**values).returning(Comment))
    ).scalar_one()


async def insert_mentions(
    session: AsyncSession, tenant_id: UUID, comment_id: UUID, user_ids: Sequence[UUID]
) -> None:
    if user_ids:
        await session.execute(
            insert(CommentMention).values(
                [
                    {"tenant_id": tenant_id, "comment_id": comment_id, "user_id": u}
                    for u in user_ids
                ]
            )
        )


async def get_comment(session: AsyncSession, comment_id: UUID) -> Comment | None:
    return (
        await session.execute(select(Comment).where(Comment.id == comment_id))
    ).scalar_one_or_none()


async def redaction_of(session: AsyncSession, comment_id: UUID) -> CommentRedaction | None:
    return (
        await session.execute(
            select(CommentRedaction).where(CommentRedaction.comment_id == comment_id)
        )
    ).scalar_one_or_none()


async def insert_redaction(session: AsyncSession, **values: object) -> bool:
    """False when the comment was already redacted (once per comment)."""
    made = await session.execute(
        pg_insert(CommentRedaction)
        .values(**values)
        .on_conflict_do_nothing()
        .returning(CommentRedaction.comment_id)
    )
    return made.scalar_one_or_none() is not None


async def list_thread(
    session: AsyncSession,
    ctx: AuthContext,
    item_id: UUID,
    version_id: UUID | None,
    *,
    shared_only: bool,
) -> Sequence[tuple[Comment, CommentRedaction | None]]:
    """A thread's comments the actor may read, oldest first, each with its redaction."""
    query = (
        select(Comment, CommentRedaction)
        .join(RequestItem, RequestItem.id == Comment.request_item_id)
        .outerjoin(CommentRedaction, CommentRedaction.comment_id == Comment.id)
        .where(
            _thread(item_id, version_id),
            visible_items(
                ctx,
                "comment.read",
                RequestItem.engagement_id,
                RequestItem.client_visible,
                RequestItem.client_assignee_user_id,
            ),
        )
        .order_by(Comment.created_at, Comment.id)
    )
    if shared_only:
        query = query.where(Comment.visibility == "shared")
    return list((await session.execute(query)).tuples().all())


async def list_mentions(
    session: AsyncSession, ctx: AuthContext, comment_ids: Sequence[UUID]
) -> dict[UUID, list[UUID]]:
    if not comment_ids:
        return {}
    rows = await session.execute(
        select(CommentMention.comment_id, CommentMention.user_id)
        .join(Comment, Comment.id == CommentMention.comment_id)
        .join(RequestItem, RequestItem.id == Comment.request_item_id)
        .where(
            CommentMention.comment_id.in_(comment_ids),
            visible_items(
                ctx,
                "comment.read",
                RequestItem.engagement_id,
                RequestItem.client_visible,
                RequestItem.client_assignee_user_id,
            ),
        )
    )
    found: dict[UUID, list[UUID]] = {}
    for comment_id, user_id in rows.tuples().all():
        found.setdefault(comment_id, []).append(user_id)
    return found


async def mark_thread_read(
    session: AsyncSession, tenant_id: UUID, user_id: UUID, item_id: UUID, version_id: UUID | None
) -> None:
    now = func.clock_timestamp()
    await session.execute(
        pg_insert(CommentRead)
        .values(
            tenant_id=tenant_id,
            user_id=user_id,
            request_item_id=item_id,
            evidence_version_id=version_id,
            last_read_at=now,
        )
        .on_conflict_do_update(constraint="comment_reads_once", set_={"last_read_at": now})
    )


async def list_comment_counts(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID, *, shared_only: bool
) -> dict[UUID, tuple[int, bool]]:
    """Per item: the comments the actor may read (its own thread and its versions'), and whether
    any written by someone else is newer than the actor's last read of that thread (Q6)."""
    newer = and_(
        Comment.author_user_id != ctx.user_id,
        or_(CommentRead.last_read_at.is_(None), Comment.created_at > CommentRead.last_read_at),
    )
    query = (
        select(
            Comment.request_item_id,
            func.count(),
            func.bool_or(newer),
        )
        .join(RequestItem, RequestItem.id == Comment.request_item_id)
        .outerjoin(
            CommentRead,
            and_(
                CommentRead.user_id == ctx.user_id,
                CommentRead.request_item_id == Comment.request_item_id,
                CommentRead.evidence_version_id.is_not_distinct_from(Comment.evidence_version_id),
            ),
        )
        .where(
            Comment.engagement_id == engagement_id,
            visible_items(
                ctx,
                "comment.read",
                RequestItem.engagement_id,
                RequestItem.client_visible,
                RequestItem.client_assignee_user_id,
            ),
        )
        .group_by(Comment.request_item_id)
    )
    if shared_only:
        query = query.where(Comment.visibility == "shared")
    rows = await session.execute(query)
    return {item: (int(count), bool(unread)) for item, count, unread in rows.tuples().all()}


# --- The client's responses (SPEC-042; TASK-106) ------------------------------------------------


async def client_responses(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> dict[UUID, ClientItemResponse]:
    """Per item the actor may read (the items' own `visible_items`), its newest response."""
    rows = (
        (
            await session.execute(
                select(ClientItemResponse)
                .join(RequestItem, RequestItem.id == ClientItemResponse.request_item_id)
                .where(
                    ClientItemResponse.engagement_id == engagement_id,
                    visible_items(
                        ctx,
                        "request_item.read",
                        RequestItem.engagement_id,
                        RequestItem.client_visible,
                        RequestItem.client_assignee_user_id,
                    ),
                )
                .order_by(ClientItemResponse.created_at)
            )
        )
        .scalars()
        .all()
    )
    return {r.request_item_id: r for r in rows}  # oldest first, so the newest wins


async def insert_client_response(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ClientItemResponse).values(**values))


async def newest_list_done(session: AsyncSession, engagement_id: UUID) -> ClientListDone | None:
    return (
        await session.execute(
            select(ClientListDone)
            .where(ClientListDone.engagement_id == engagement_id)
            .order_by(ClientListDone.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def insert_list_done(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ClientListDone).values(**values))


# --- Search (SPEC-302; TASK-303) ----------------------------------------------------------------


def like_pattern(q: str) -> str:
    """A case-insensitive substring pattern with `%`, `_` and `\\` taken literally."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def search_items(
    session: AsyncSession, ctx: AuthContext, q: str, limit: int
) -> Sequence[RequestItem]:
    """Items whose description or area contains `q`, newest first, through `visible_items()`."""
    pattern = like_pattern(q)
    return (
        (
            await session.execute(
                select(RequestItem)
                .where(
                    or_(
                        RequestItem.description.ilike(pattern, escape="\\"),
                        RequestItem.audit_area.ilike(pattern, escape="\\"),
                    ),
                    visible_items(
                        ctx,
                        "request_item.read",
                        RequestItem.engagement_id,
                        RequestItem.client_visible,
                        RequestItem.client_assignee_user_id,
                    ),
                )
                .order_by(RequestItem.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


# --- Binders (P-06-T07; C5; DEC-31) --------------------------------------------------------------


async def get_binder(
    session: AsyncSession, binder_id: UUID, *, lock: bool = False
) -> RequestList | None:
    """The binder; `lock` holds its row until the transaction ends (one lifecycle move at a
    time)."""
    query = select(RequestList).where(RequestList.id == binder_id)
    if lock:
        query = query.with_for_update()
    return (await session.execute(query)).scalar_one_or_none()


async def next_part(session: AsyncSession, work_item_id: UUID, kind: str) -> int:
    """The part a new binder of `kind` on the work item takes: one more than the highest."""
    highest = await session.scalar(
        select(func.max(RequestList.part)).where(
            RequestList.work_item_id == work_item_id, RequestList.kind == kind
        )
    )
    return 1 if highest is None else int(highest) + 1


async def insert_binder(session: AsyncSession, **values: object) -> RequestList:
    return (
        await session.execute(insert(RequestList).values(**values).returning(RequestList))
    ).scalar_one()


async def set_binder(
    session: AsyncSession, binder_id: UUID, *, allowed_from: tuple[str, ...], **values: object
) -> bool:
    """Change the binder's lifecycle stamps if its status is one of `allowed_from`."""
    done = await session.execute(
        update(RequestList)
        .where(RequestList.id == binder_id, RequestList.status.in_(allowed_from))
        .values(**values)
        .returning(RequestList.id)
    )
    return done.first() is not None


async def binder_categories(session: AsyncSession, binder_id: UUID) -> Sequence[RequestCategory]:
    """A binder's sections in order, for a caller that authorised the binder (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(RequestCategory)
                .where(RequestCategory.request_list_id == binder_id)
                .order_by(RequestCategory.position, RequestCategory.id)
            )
        )
        .scalars()
        .all()
    )


async def insert_categories(
    session: AsyncSession, tenant_id: UUID, binder_id: UUID, names: Sequence[str]
) -> dict[str, UUID]:
    """The binder's sections, in this order; their ids by name."""
    if not names:
        return {}
    made = await session.execute(
        insert(RequestCategory)
        .values(
            [
                {"tenant_id": tenant_id, "request_list_id": binder_id, "name": n, "position": p}
                for p, n in enumerate(names)
            ]
        )
        .returning(RequestCategory.name, RequestCategory.id)
    )
    return {name: category_id for name, category_id in made}


async def binder_items(session: AsyncSession, binder_id: UUID) -> Sequence[RequestItem]:
    """Every request of a binder that isn't deleted, oldest first, for a caller that authorised
    the binder: its counts, its publish and its client preview (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(RequestItem)
                .where(RequestItem.request_list_id == binder_id, RequestItem.deleted_at.is_(None))
                .order_by(RequestItem.created_at, RequestItem.id)
            )
        )
        .scalars()
        .all()
    )


async def list_binder_requests(
    session: AsyncSession,
    ctx: AuthContext,
    binder_id: UUID,
    category: UUID | None,
    after: Position | None,
    limit: int,
) -> tuple[Sequence[RequestItem], dict[str, int], tuple[int, bool]]:
    """A keyset page of a binder's requests the reader may see (SPEC-020's client conditions
    included), oldest first, with the counts per status and the total over the same filter."""
    query = select(RequestItem).where(
        RequestItem.request_list_id == binder_id,
        RequestItem.deleted_at.is_(None),
        visible_items(
            ctx,
            "request_item.read",
            RequestItem.engagement_id,
            RequestItem.client_visible,
            RequestItem.client_assignee_user_id,
        ),
    )
    if category is not None:
        query = query.where(RequestItem.category_id == category)
    paged = keyset(
        query,
        sort=cast(ColumnElement[object], RequestItem.created_at.expression),
        id_column=cast(ColumnElement[object], RequestItem.id.expression),
        after=after,
        limit=limit,
    )
    rows = (await session.execute(paged)).scalars().all()
    counts = await status_counts(session, query, RequestItem.status.expression)
    return rows, counts, await capped_total(session, query)


async def list_client_preview(
    session: AsyncSession, ctx: AuthContext, binder_id: UUID
) -> Sequence[RequestItem]:
    """A binder's client-visible requests the reader may see, oldest first (the preview)."""
    return (
        (
            await session.execute(
                select(RequestItem)
                .where(
                    RequestItem.request_list_id == binder_id,
                    RequestItem.deleted_at.is_(None),
                    RequestItem.client_visible.is_(True),
                    visible_items(
                        ctx,
                        "request_item.read",
                        RequestItem.engagement_id,
                        RequestItem.client_visible,
                        RequestItem.client_assignee_user_id,
                    ),
                )
                .order_by(RequestItem.created_at, RequestItem.id)
            )
        )
        .scalars()
        .all()
    )


async def upload_counts(session: AsyncSession, item_ids: Sequence[UUID]) -> dict[UUID, int]:
    """Fulfilments per item, for items the caller already read."""
    if not item_ids:
        return {}
    rows = await session.execute(
        select(Fulfilment.request_item_id, func.count())
        .where(Fulfilment.request_item_id.in_(item_ids), live_fulfilment())
        .group_by(Fulfilment.request_item_id)
    )
    return {item: int(n) for item, n in rows}


async def assigned_in_binder(session: AsyncSession, binder_id: UUID, user_id: UUID) -> bool:
    """Whether a client-visible request of the binder is assigned to this client user."""
    found = await session.scalar(
        select(RequestItem.id)
        .where(
            RequestItem.request_list_id == binder_id,
            RequestItem.deleted_at.is_(None),
            RequestItem.client_visible.is_(True),
            RequestItem.client_assignee_user_id == user_id,
        )
        .limit(1)
    )
    return found is not None


async def stamp_sent(
    session: AsyncSession, item_ids: Sequence[UUID], *, at: datetime | None, by: UUID | None
) -> None:
    """Mark requests sent by a publish (or, with None, unsent again by its Undo)."""
    if item_ids:
        await session.execute(
            update(RequestItem).where(RequestItem.id.in_(item_ids)).values(sent_at=at, sent_by=by)
        )


async def recipient_rows(session: AsyncSession, binder_id: UUID) -> Sequence[BinderRecipient]:
    """A binder's recipient history (insert-only), for a caller that authorised the binder
    (LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(BinderRecipient)
                .where(BinderRecipient.binder_id == binder_id)
                .order_by(BinderRecipient.added_at, BinderRecipient.id)
            )
        )
        .scalars()
        .all()
    )


async def insert_recipient_rows(session: AsyncSession, rows: Sequence[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(BinderRecipient).values(list(rows)))


async def open_binders(
    session: AsyncSession, *, engagement_id: UUID | None, work_item_id: UUID | None
) -> Sequence[RequestList]:
    """Binders not yet closed on a work item (else an engagement), locked, for the platform's
    close rule (LIST_EXEMPT: the system acting on a C1 fact, never returned to a caller)."""
    query = select(RequestList).where(RequestList.status != "closed")
    if work_item_id is not None:
        query = query.where(RequestList.work_item_id == work_item_id)
    elif engagement_id is not None:
        query = query.where(RequestList.engagement_id == engagement_id)
    else:
        return []
    return (await session.execute(query.with_for_update())).scalars().all()


# --- P-06-T11: the binders index read model (BND-01) --------------------------------------------

IndexQuery = Select[*tuple[Any, ...]]  # Any: the binder and its joined facts' columns


def binder_index(ctx: AuthContext, work_items: Subquery) -> IndexQuery:
    """Every binder the caller may read, joined to its work item's facts (engagements'
    `work_item_index`) and its activity projection. `visible()` applies here, so walled and
    out-of-team binders are absent from rows, tiles, totals and facets alike (INV-3, DEC-43).
    The caller adds the filters; Any: the row is the binder and its joined facts."""
    return (
        select(
            RequestList,
            work_items.c.kind.label("work_item_kind"),
            work_items.c.name.label("work_item_name"),
            work_items.c.client_name,
            work_items.c.office_id,
            work_items.c.office_name,
            work_items.c.season,
            work_items.c.preparer_user_id,
            BinderActivity.last_client_activity_at,
        )
        .join(work_items, work_items.c.id == RequestList.work_item_id)
        .outerjoin(
            BinderActivity,
            and_(
                BinderActivity.tenant_id == RequestList.tenant_id,
                BinderActivity.binder_id == RequestList.id,
            ),
        )
        .where(visible(ctx, "binder.read", RequestList.engagement_id))
    )


DONE_REQUESTS: tuple[str, ...] = ("uploaded", "received", "not_applicable")
OPEN_REQUESTS: tuple[str, ...] = ("requested", "returned")


async def binder_progress(
    session: AsyncSession, ctx: AuthContext, binder_ids: Sequence[UUID], today: date
) -> dict[UUID, tuple[int, int, int, int, datetime | None, datetime | None]]:
    """Per binder of a page the caller listed: (done, total, overdue, requested, first and last
    `requested_at` of the requests still waiting on the client). Deleted drafts don't count.
    Overdue is an open request past its due date, its own or the binder's default."""
    if not binder_ids:
        return {}
    due = func.coalesce(RequestItem.due_on, RequestList.default_due_on)
    waiting = and_(RequestItem.status == "requested", RequestItem.client_visible.is_(True))
    rows = await session.execute(
        select(
            RequestItem.request_list_id,
            func.count().filter(RequestItem.status.in_(DONE_REQUESTS)),
            func.count(),
            func.count().filter(RequestItem.status.in_(OPEN_REQUESTS), due < today),
            func.count().filter(waiting),
            func.min(RequestItem.requested_at).filter(waiting),
            func.max(RequestItem.requested_at).filter(waiting),
        )
        .join(RequestList, RequestList.id == RequestItem.request_list_id)
        .where(
            RequestItem.request_list_id.in_(binder_ids),
            RequestItem.deleted_at.is_(None),
            visible(ctx, "binder.read", RequestList.engagement_id),
        )
        .group_by(RequestItem.request_list_id)
    )
    return {
        binder: (int(done), int(total), int(overdue), int(requested), first, last)
        for binder, done, total, overdue, requested, first, last in rows
    }


async def touch_client_activity(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    binder_id: UUID,
    work_item_id: UUID | None,
    status: str,
    at: datetime,
) -> None:
    """The projection after a client act on the binder (P-06-T11): its status and when the
    client last acted. Inside the caller's unit of work, whose audit event records the act."""
    await session.execute(
        pg_insert(BinderActivity)
        .values(
            tenant_id=tenant_id,
            binder_id=binder_id,
            work_item_id=work_item_id,
            status=status,
            last_client_activity_at=at,
        )
        .on_conflict_do_update(
            index_elements=[BinderActivity.tenant_id, BinderActivity.binder_id],
            set_={
                "status": status,
                "last_client_activity_at": at,
                "updated_at": func.abacus_now(),
            },
        )
    )


# P-07-T08: items waiting on the client (service.OPEN_FOR_CLIENT).
_WAITING_ON_CLIENT = ("requested", "returned")


def open_requests_by_engagement() -> Select[UUID, int]:
    """`(engagement_id, n)`: items waiting on the client, per engagement, for the clients
    index's open-request count (registered with organisations)."""
    return (
        select(RequestItem.engagement_id, func.count().label("n"))
        .where(RequestItem.status.in_(_WAITING_ON_CLIENT))
        .group_by(RequestItem.engagement_id)
    )


# --- P-06-T10: the request lifecycle's writes ----------------------------------------------------


async def set_item_fields(
    session: AsyncSession, item_id: UUID, values: Mapping[str, object]
) -> None:
    """Set the named columns of one request the caller locked and authorised."""
    if values:
        await session.execute(
            update(RequestItem).where(RequestItem.id == item_id).values(**values)
        )


async def insert_delegation(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    request_item_id: UUID,
    contact_id: UUID,
    grant_id: UUID,
    granted_by: UUID,
) -> None:
    await session.execute(
        text(
            "INSERT INTO request_delegations (tenant_id, request_item_id, contact_id, grant_id, "
            "granted_by) VALUES (:tenant, :item, :contact, :grant, :by)"
        ),
        {
            "tenant": tenant_id,
            "item": request_item_id,
            "contact": contact_id,
            "grant": grant_id,
            "by": granted_by,
        },
    )


async def insert_upload_intent(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    request_item_id: UUID,
    user_id: UUID,
    files_expected: int,
) -> datetime:
    """A 90-second upload hint; when it expires."""
    return (
        await session.execute(
            text(
                "INSERT INTO request_upload_intents (tenant_id, request_item_id, user_id, "
                "files_expected) VALUES (:tenant, :item, :user, :files) RETURNING expires_at"
            ),
            {
                "tenant": tenant_id,
                "item": request_item_id,
                "user": user_id,
                "files": files_expected,
            },
        )
    ).scalar_one()


async def live_upload_intents(session: AsyncSession, item_ids: Sequence[UUID]) -> dict[UUID, int]:
    """Files expected by unexpired intents, per request the caller already read
    (LIST_EXEMPT: the binder's requests, authorised by the caller)."""
    if not item_ids:
        return {}
    rows = await session.execute(
        text(
            "SELECT request_item_id, sum(files_expected) FROM request_upload_intents "
            "WHERE request_item_id = ANY(:items) AND expires_at > clock_timestamp() "
            "GROUP BY request_item_id"
        ),
        {"items": list(item_ids)},
    )
    return {item: int(n) for item, n in rows.tuples().all()}


async def client_home_items(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[tuple[RequestItem, RequestList, int]]:
    """P-08-T13 (POR-02): the engagement's live client-visible requests in a published (or done)
    binder, each with its binder and how many of its files the firm matched (`rule`, `agent`)."""
    matched = (
        select(func.count())
        .where(
            Fulfilment.request_item_id == RequestItem.id,
            Fulfilment.created_by_kind.in_(("rule", "agent")),
            live_fulfilment(),
        )
        .correlate(RequestItem)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(RequestItem, RequestList, matched)
        .join(RequestList, RequestList.id == RequestItem.request_list_id)
        .where(
            RequestItem.engagement_id == engagement_id,
            RequestItem.deleted_at.is_(None),
            RequestItem.client_visible.is_(True),
            RequestList.status.in_(("published", "complete")),
            visible_items(
                ctx,
                "request_item.read",
                RequestItem.engagement_id,
                RequestItem.client_visible,
                RequestItem.client_assignee_user_id,
            ),
        )
        .order_by(RequestItem.created_at, RequestItem.id)
    )
    return [(item, binder, int(count)) for item, binder, count in rows.all()]


async def follow_up_items(
    session: AsyncSession,
    ctx: AuthContext,
    binder_ids: Sequence[UUID],
    item_ids: Sequence[UUID],
) -> Sequence[tuple[RequestItem, date | None]]:
    """P-06-T14: the open (Requested or Returned), client-visible, never-deleted requests of
    Published binders, among these binders or these ids, that the caller may read (walls and
    independence apply), with their due date (their own, else the binder's). A Draft,
    Unpublished, Complete or Closed binder's requests are never chased."""
    if not binder_ids and not item_ids:
        return []
    due = func.coalesce(RequestItem.due_on, RequestList.default_due_on)
    picked: list[ColumnElement[bool]] = []
    if binder_ids:
        picked.append(RequestItem.request_list_id.in_(list(binder_ids)))
    if item_ids:
        picked.append(RequestItem.id.in_(list(item_ids)))
    rows = await session.execute(
        select(RequestItem, due)
        .join(RequestList, RequestList.id == RequestItem.request_list_id)
        .where(
            or_(*picked),
            RequestItem.status.in_(("requested", "returned")),
            RequestItem.client_visible,
            RequestItem.deleted_at.is_(None),
            RequestList.status == "published",
            visible(ctx, "request_item.read", RequestItem.engagement_id),
        )
        .order_by(RequestItem.engagement_id, due, RequestItem.created_at, RequestItem.id)
    )
    return [(item, d) for item, d in rows.all()]


async def binders_recipient_rows(
    session: AsyncSession, binder_ids: Sequence[UUID]
) -> Sequence[BinderRecipient]:
    """P-06-T14: the recipient histories of binders whose requests the caller just read through
    `visible()` (`follow_up_items`) (LIST_EXEMPT)."""
    if not binder_ids:
        return []
    return (
        (
            await session.execute(
                select(BinderRecipient)
                .where(BinderRecipient.binder_id.in_(list(binder_ids)))
                .order_by(BinderRecipient.added_at, BinderRecipient.id)
            )
        )
        .scalars()
        .all()
    )


async def binder_statuses(
    session: AsyncSession, ctx: AuthContext, binder_ids: Sequence[UUID]
) -> dict[UUID, str]:
    """P-06-T14: the status of each of these binders the caller may read (walls apply)."""
    if not binder_ids:
        return {}
    rows = await session.execute(
        select(RequestList.id, RequestList.status).where(
            RequestList.id.in_(list(binder_ids)),
            visible(ctx, "binder.read", RequestList.engagement_id),
        )
    )
    return {i: str(st) for i, st in rows.all()}
