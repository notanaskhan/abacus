"""Evidence data access: evidence items and versions, and review decisions, assignments and the
reason-code catalogue (ADR-008, ADR-103; SPEC-004 Q4)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.evidence.models import (
    EvidenceItem,
    EvidenceVersion,
    InboxFile,
    ReviewAssignment,
    ReviewDecision,
    UploadCheck,
    UploadExtraction,
)
from abacus.modules.identity.api import AuthContext, visible

# Serialises version numbering per item for the rest of the transaction. Row locks would need
# UPDATE privilege on the item, which the app deliberately doesn't have. Two-key form: the first
# key namespaces evidence-version locks from any other advisory lock.
_EVIDENCE_LOCK_SPACE = 9_004
_LOCK_ITEM = text("SELECT pg_advisory_xact_lock(:space, hashtext(:item))")


async def insert_item(
    session: AsyncSession,
    *,
    item_id: UUID,
    tenant_id: UUID,
    engagement_id: UUID,
    title: str,
    created_by_kind: str,
    created_by_id: str,
) -> None:
    await session.execute(
        insert(EvidenceItem).values(
            id=item_id,
            tenant_id=tenant_id,
            engagement_id=engagement_id,
            title=title,
            created_by_kind=created_by_kind,
            created_by_id=created_by_id,
        )
    )


async def next_version_no(session: AsyncSession, evidence_item_id: UUID) -> int:
    await session.execute(
        _LOCK_ITEM, {"space": _EVIDENCE_LOCK_SPACE, "item": str(evidence_item_id)}
    )
    current = (
        await session.execute(
            select(func.max(EvidenceVersion.version_no)).where(
                EvidenceVersion.evidence_item_id == evidence_item_id
            )
        )
    ).scalar_one_or_none()
    return (current or 0) + 1


async def insert_version(
    session: AsyncSession,
    *,
    version_id: UUID,
    tenant_id: UUID,
    engagement_id: UUID,
    evidence_item_id: UUID,
    version_no: int,
    fingerprint: str,
    storage_key: str,
    storage_version_id: str,
    size_bytes: int,
    media_type: str,
    source: str,
    method: str,
    pulled_at: datetime | None,
    period_start: date | None,
    period_end: date | None,
    client_entity_id: UUID | None,
    snapshot_id: UUID | None,
    idempotency_key: str | None,
    upload_note: str | None = None,
) -> EvidenceVersion:
    return (
        await session.execute(
            insert(EvidenceVersion)
            .values(
                id=version_id,
                tenant_id=tenant_id,
                engagement_id=engagement_id,
                evidence_item_id=evidence_item_id,
                version_no=version_no,
                fingerprint=fingerprint,
                storage_key=storage_key,
                storage_version_id=storage_version_id,
                size_bytes=size_bytes,
                media_type=media_type,
                source=source,
                method=method,
                pulled_at=pulled_at,
                period_start=period_start,
                period_end=period_end,
                client_entity_id=client_entity_id,
                snapshot_id=snapshot_id,
                idempotency_key=idempotency_key,
                upload_note=upload_note,
            )
            .returning(EvidenceVersion)
        )
    ).scalar_one()


async def get_version(session: AsyncSession, version_id: UUID) -> EvidenceVersion | None:
    return (
        await session.execute(select(EvidenceVersion).where(EvidenceVersion.id == version_id))
    ).scalar_one_or_none()


async def get_item(session: AsyncSession, item_id: UUID) -> EvidenceItem | None:
    return (
        await session.execute(select(EvidenceItem).where(EvidenceItem.id == item_id))
    ).scalar_one_or_none()


async def version_for_key(session: AsyncSession, idempotency_key: str) -> EvidenceVersion | None:
    return (
        await session.execute(
            select(EvidenceVersion).where(EvidenceVersion.idempotency_key == idempotency_key)
        )
    ).scalar_one_or_none()


async def list_versions(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[EvidenceVersion]:
    """The engagement's evidence versions the caller may read, oldest first."""
    return (
        (
            await session.execute(
                select(EvidenceVersion)
                .where(
                    EvidenceVersion.engagement_id == engagement_id,
                    visible(ctx, "evidence.read", EvidenceVersion.engagement_id),
                )
                .order_by(EvidenceVersion.created_at, EvidenceVersion.id)
            )
        )
        .scalars()
        .all()
    )


# --- review (SPEC-004) ------------------------------------------------------------------------


async def list_review_state(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> tuple[Sequence[EvidenceVersion], set[UUID], dict[UUID, UUID | None]]:
    """For the queue: the engagement's versions the caller may review, which are decided, and who
    has taken which."""
    seen = visible(ctx, "review.read", EvidenceVersion.engagement_id)
    versions = (
        (
            await session.execute(
                select(EvidenceVersion).where(EvidenceVersion.engagement_id == engagement_id, seen)
            )
        )
        .scalars()
        .all()
    )
    decided = set(
        (
            await session.execute(
                select(ReviewDecision.evidence_version_id).where(
                    ReviewDecision.engagement_id == engagement_id,
                    visible(ctx, "review.read", ReviewDecision.engagement_id),
                )
            )
        )
        .scalars()
        .all()
    )
    taken = {
        version_id: assignee
        for version_id, assignee in (
            await session.execute(
                select(
                    ReviewAssignment.evidence_version_id, ReviewAssignment.assignee_user_id
                ).where(
                    ReviewAssignment.engagement_id == engagement_id,
                    visible(ctx, "review.read", ReviewAssignment.engagement_id),
                )
            )
        ).all()
    }
    return versions, decided, taken


async def decision_for(session: AsyncSession, version_id: UUID) -> ReviewDecision | None:
    return (
        await session.execute(
            select(ReviewDecision).where(ReviewDecision.evidence_version_id == version_id)
        )
    ).scalar_one_or_none()


async def insert_decision(session: AsyncSession, *, values: dict[str, object]) -> None:
    await session.execute(insert(ReviewDecision).values(**values))


async def assignment_for(
    session: AsyncSession, engagement_id: UUID, version_id: UUID
) -> ReviewAssignment | None:
    """The version's assignment within this engagement only (TASK-019 security review H1)."""
    return (
        await session.execute(
            select(ReviewAssignment)
            .where(
                ReviewAssignment.engagement_id == engagement_id,
                ReviewAssignment.evidence_version_id == version_id,
            )
            .with_for_update()
        )
    ).scalar_one_or_none()


async def take_assignment(
    session: AsyncSession, *, tenant_id: UUID, engagement_id: UUID, version_id: UUID, me: UUID
) -> bool:
    """Take the version unless someone else holds it, in one statement (no race between two
    first takes): False when another person has it."""
    taken = await session.execute(
        pg_insert(ReviewAssignment)
        .values(
            tenant_id=tenant_id,
            evidence_version_id=version_id,
            engagement_id=engagement_id,
            assignee_user_id=me,
            assigned_by=me,
        )
        .on_conflict_do_update(
            index_elements=[ReviewAssignment.tenant_id, ReviewAssignment.evidence_version_id],
            set_={
                "assignee_user_id": me,
                "assigned_by": me,
                "assigned_at": func.clock_timestamp(),
            },
            where=(ReviewAssignment.assignee_user_id.is_(None))
            | (ReviewAssignment.assignee_user_id == me),
        )
        .returning(ReviewAssignment.evidence_version_id)
    )
    return taken.scalar_one_or_none() is not None


async def put_assignment(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    version_id: UUID,
    assignee: UUID | None,
    assigned_by: UUID,
) -> None:
    """Set who has taken the version (None: released)."""
    await session.execute(
        pg_insert(ReviewAssignment)
        .values(
            tenant_id=tenant_id,
            evidence_version_id=version_id,
            engagement_id=engagement_id,
            assignee_user_id=assignee,
            assigned_by=assigned_by,
        )
        .on_conflict_do_update(
            index_elements=[ReviewAssignment.tenant_id, ReviewAssignment.evidence_version_id],
            set_={
                "assignee_user_id": assignee,
                "assigned_by": assigned_by,
                "assigned_at": func.clock_timestamp(),
            },
        )
    )


async def clear_assignment(
    session: AsyncSession, engagement_id: UUID, version_id: UUID, by: UUID
) -> None:
    await session.execute(
        update(ReviewAssignment)
        .where(
            ReviewAssignment.engagement_id == engagement_id,
            ReviewAssignment.evidence_version_id == version_id,
        )
        .values(assignee_user_id=None, assigned_by=by, assigned_at=func.clock_timestamp())
    )


async def release_assignments_of(
    session: AsyncSession, engagement_id: UUID, user_id: UUID, by: UUID
) -> list[UUID]:
    """Clear `user_id`'s review assignments on the engagement (SPEC-017 AC-5): their versions."""
    released = await session.execute(
        update(ReviewAssignment)
        .where(
            ReviewAssignment.engagement_id == engagement_id,
            ReviewAssignment.assignee_user_id == user_id,
        )
        .values(assignee_user_id=None, assigned_by=by, assigned_at=func.clock_timestamp())
        .returning(ReviewAssignment.evidence_version_id)
    )
    return [row[0] for row in released.all()]


async def reason_codes(
    session: AsyncSession, applies_to: str
) -> Sequence[tuple[str, str, str, bool]]:
    """The active catalogue for a decision kind, through its SECURITY DEFINER function (0015)."""
    listed = func.review_reason_codes_list(applies_to).table_valued(
        "code", "label", "description", "requires_note"
    )
    rows = await session.execute(
        select(listed.c.code, listed.c.label, listed.c.description, listed.c.requires_note)
    )
    return [(str(r[0]), str(r[1]), str(r[2]), bool(r[3])) for r in rows.all()]


async def snapshots_of_engagement(session: AsyncSession, engagement_id: UUID) -> list[UUID]:
    """The ledger snapshots behind the engagement's evidence versions (SPEC-006 scope)."""
    rows = await session.execute(
        select(EvidenceVersion.snapshot_id)
        .where(
            EvidenceVersion.engagement_id == engagement_id,
            EvidenceVersion.snapshot_id.is_not(None),
        )
        .distinct()
    )
    return [r for r in rows.scalars().all() if r is not None]


async def uploaded_versions(
    session: AsyncSession, version_ids: Sequence[UUID]
) -> Sequence[tuple[EvidenceVersion, EvidenceItem]]:
    """The uploaded ones among a request item's versions, newest first, for a caller that
    authorised `evidence.read` on that item (SPEC-020; LIST_EXEMPT)."""
    if not version_ids:
        return []
    rows = await session.execute(
        select(EvidenceVersion, EvidenceItem)
        .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
        .where(EvidenceVersion.id.in_(version_ids), EvidenceVersion.method == "uploaded")
        .order_by(EvidenceVersion.created_at.desc(), EvidenceVersion.id)
    )
    return [(version, item) for version, item in rows.tuples().all()]


async def fingerprint_among(
    session: AsyncSession, version_ids: Sequence[UUID], fingerprint: str
) -> bool:
    """Whether any of these versions has this content (SPEC-020: duplicate uploads)."""
    if not version_ids:
        return False
    found = await session.execute(
        select(EvidenceVersion.id)
        .where(EvidenceVersion.id.in_(version_ids), EvidenceVersion.fingerprint == fingerprint)
        .limit(1)
    )
    return found.scalar_one_or_none() is not None


async def item_versions_with_decisions(
    session: AsyncSession, request_item_id: UUID, version_ids: Sequence[UUID]
) -> Sequence[tuple[EvidenceVersion, EvidenceItem, ReviewDecision | None]]:
    """A request item's versions, newest first, each with its evidence item and its decision on
    this item, for a caller that authorised `evidence.read` on it (SPEC-021; LIST_EXEMPT)."""
    if not version_ids:
        return []
    rows = await session.execute(
        select(EvidenceVersion, EvidenceItem, ReviewDecision)
        .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
        .outerjoin(
            ReviewDecision,
            (ReviewDecision.evidence_version_id == EvidenceVersion.id)
            & (ReviewDecision.request_item_id == request_item_id),
        )
        .where(EvidenceVersion.id.in_(version_ids))
        .order_by(EvidenceVersion.created_at.desc(), EvidenceVersion.id)
    )
    return list(rows.tuples().all())


async def methods_of(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID, version_ids: Sequence[UUID]
) -> dict[UUID, str]:
    """How each of these versions arrived (retrieved or uploaded), for the board summary."""
    if not version_ids:
        return {}
    rows = await session.execute(
        select(EvidenceVersion.id, EvidenceVersion.method).where(
            EvidenceVersion.id.in_(version_ids),
            EvidenceVersion.engagement_id == engagement_id,
            visible(ctx, "evidence.read", EvidenceVersion.engagement_id),
        )
    )
    return {version_id: method for version_id, method in rows.tuples().all()}


# --- The engagement inbox (SPEC-023; TASK-039) -------------------------------------------------


async def insert_inbox_file(session: AsyncSession, **values: object) -> InboxFile:
    return (
        await session.execute(insert(InboxFile).values(**values).returning(InboxFile))
    ).scalar_one()


async def waiting_with_fingerprint(
    session: AsyncSession, engagement_id: UUID, fingerprint: str
) -> bool:
    found = await session.execute(
        select(InboxFile.id).where(
            InboxFile.engagement_id == engagement_id,
            InboxFile.fingerprint == fingerprint,
            InboxFile.status == "waiting",
        )
    )
    return found.scalar_one_or_none() is not None


async def waiting_inbox(session: AsyncSession, engagement_id: UUID) -> Sequence[InboxFile]:
    """The engagement's waiting files, oldest first, for a caller that authorised on the
    engagement; the service narrows them by role (SPEC-023; LIST_EXEMPT)."""
    return (
        (
            await session.execute(
                select(InboxFile)
                .where(InboxFile.engagement_id == engagement_id, InboxFile.status == "waiting")
                .order_by(InboxFile.created_at, InboxFile.id)
            )
        )
        .scalars()
        .all()
    )


async def lock_inbox_file(session: AsyncSession, file_id: UUID) -> InboxFile | None:
    return (
        await session.execute(select(InboxFile).where(InboxFile.id == file_id).with_for_update())
    ).scalar_one_or_none()


async def decide_inbox_file(session: AsyncSession, file_id: UUID, **values: object) -> None:
    await session.execute(
        update(InboxFile)
        .where(InboxFile.id == file_id, InboxFile.status == "waiting")
        .values(decided_at=func.clock_timestamp(), **values)
    )


async def get_inbox_file(session: AsyncSession, file_id: UUID) -> InboxFile | None:
    return (
        await session.execute(select(InboxFile).where(InboxFile.id == file_id))
    ).scalar_one_or_none()


async def extraction_for(
    session: AsyncSession,
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
    extractor_version: str,
) -> UploadExtraction | None:
    """SPEC-029 (TASK-054): the upload's extraction by this extractor version, if made."""
    source = (
        UploadExtraction.evidence_version_id == evidence_version_id
        if evidence_version_id is not None
        else UploadExtraction.inbox_file_id == inbox_file_id
    )
    return (
        await session.execute(
            select(UploadExtraction).where(
                source, UploadExtraction.extractor_version == extractor_version
            )
        )
    ).scalar_one_or_none()


async def insert_extraction(session: AsyncSession, **values: object) -> UploadExtraction | None:
    """The new extraction, or None when this source already has one by this version."""
    by_version = values.get("evidence_version_id") is not None
    where = "evidence_version_id" if by_version else "inbox_file_id"
    present = (
        UploadExtraction.evidence_version_id.is_not(None)
        if by_version
        else UploadExtraction.inbox_file_id.is_not(None)
    )
    return (
        await session.execute(
            pg_insert(UploadExtraction)
            .values(**values)
            .on_conflict_do_nothing(
                index_elements=["tenant_id", where, "extractor_version"],
                index_where=present,
            )
            .returning(UploadExtraction)
        )
    ).scalar_one_or_none()


async def other_version_with_fingerprint(
    session: AsyncSession, engagement_id: UUID, fingerprint: str, version_id: UUID
) -> UUID | None:
    """SPEC-029 AC-8: the earliest other version of this engagement with the same file."""
    return (
        await session.execute(
            select(EvidenceVersion.id)
            .where(
                EvidenceVersion.engagement_id == engagement_id,
                EvidenceVersion.fingerprint == fingerprint,
                EvidenceVersion.id != version_id,
            )
            .order_by(EvidenceVersion.created_at, EvidenceVersion.id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def checks_exist(
    session: AsyncSession, version_id: UUID, checker_version: str, document_kind: str | None
) -> bool:
    kind = (
        UploadCheck.document_kind == document_kind
        if document_kind is not None
        else UploadCheck.document_kind.is_(None)
    )
    found = await session.execute(
        select(UploadCheck.id)
        .where(
            UploadCheck.evidence_version_id == version_id,
            UploadCheck.checker_version == checker_version,
            kind,
        )
        .limit(1)
    )
    return found.scalar_one_or_none() is not None


async def insert_checks(session: AsyncSession, rows: Sequence[dict[str, object]]) -> int:
    """Each check once per version, checker version and kind; returns how many were new."""
    if not rows:
        return 0
    result = await session.execute(
        pg_insert(UploadCheck)
        .values(list(rows))
        .on_conflict_do_nothing()
        .returning(UploadCheck.id)
    )
    return len(result.scalars().all())


async def latest_checks(session: AsyncSession, version_id: UUID) -> Sequence[UploadCheck]:
    """The version's checks from its most recent run (the latest checker version and kind)."""
    newest = (
        select(UploadCheck.created_at)
        .where(UploadCheck.evidence_version_id == version_id)
        .order_by(UploadCheck.created_at.desc())
        .limit(1)
        .scalar_subquery()
    )
    latest = (
        select(UploadCheck.checker_version, UploadCheck.document_kind)
        .where(UploadCheck.evidence_version_id == version_id, UploadCheck.created_at == newest)
        .limit(1)
    )
    run = (await session.execute(latest)).first()
    if run is None:
        return []
    kind = (
        UploadCheck.document_kind == run.document_kind
        if run.document_kind is not None
        else UploadCheck.document_kind.is_(None)
    )
    return (
        (
            await session.execute(
                select(UploadCheck)
                .where(
                    UploadCheck.evidence_version_id == version_id,
                    UploadCheck.checker_version == run.checker_version,
                    kind,
                )
                .order_by(UploadCheck.audience, UploadCheck.check_code)
            )
        )
        .scalars()
        .all()
    )
