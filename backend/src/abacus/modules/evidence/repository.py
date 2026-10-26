"""Evidence data access: evidence items and versions, and review decisions, assignments and the
reason-code catalogue (ADR-008, ADR-103; SPEC-004 Q4)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import (
    ARRAY,
    Boolean,
    ColumnElement,
    Integer,
    LargeBinary,
    Numeric,
    Text,
    and_,
    column,
    exists,
    func,
    insert,
    or_,
    select,
    table,
    text,
    true,
    update,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from abacus.modules.evidence.models import (
    Citation,
    CitationEvent,
    EvidenceItem,
    EvidenceObjectKey,
    EvidencePage,
    EvidenceVersion,
    EvidenceVersionVoid,
    EvidenceWithdrawal,
    InboxFile,
    PiiRegion,
    PiiScanRun,
    ReviewAssignment,
    ReviewDecision,
    UploadCheck,
    UploadExtraction,
    UploadPreview,
    UploadPreviewPage,
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
    storage_mode: str = "content_addressed",
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
                storage_mode=storage_mode,
            )
            .returning(EvidenceVersion)
        )
    ).scalar_one()


async def insert_object_key(
    session: AsyncSession, *, tenant_id: UUID, version_id: UUID, key_id: str, wrapped: bytes
) -> None:
    """A detached-key version's wrapped data key, in the version's own unit of work."""
    await session.execute(
        insert(EvidenceObjectKey).values(
            tenant_id=tenant_id, evidence_version_id=version_id, key_id=key_id, wrapped_key=wrapped
        )
    )


def not_withdrawn() -> ColumnElement[bool]:
    """P-06-T19 (ADR-162 §4): the version was not withdrawn by the client, nor retired with a
    voided rule link (R-01 Story 2.2; 0159). Every read of versions applies it: such a version is
    as if it never arrived (the audit trail apart)."""
    return and_(
        ~(
            select(EvidenceWithdrawal.evidence_version_id)
            .where(EvidenceWithdrawal.evidence_version_id == EvidenceVersion.id)
            .exists()
        ),
        ~(
            select(EvidenceVersionVoid.evidence_version_id)
            .where(EvidenceVersionVoid.evidence_version_id == EvidenceVersion.id)
            .exists()
        ),
    )


async def retire_voided_version(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    engagement_id: UUID,
    version_id: UUID,
    fulfilment_id: UUID,
    voided_by: UUID,
) -> None:
    """R-01 Story 2.2: the version a voided rule link made leaves every evidence read."""
    await session.execute(
        insert(EvidenceVersionVoid).values(
            tenant_id=tenant_id,
            evidence_version_id=version_id,
            engagement_id=engagement_id,
            fulfilment_id=fulfilment_id,
            voided_by=voided_by,
        )
    )


def shown_citation() -> ColumnElement[bool]:
    """A citation anyone may read: not from a shadow run (SPEC-036 AC-5; 0158) and its source
    not withdrawn (`live_citation_source`)."""
    return and_(Citation.shadow.is_(False), live_citation_source())


def live_citation_source() -> ColumnElement[bool]:
    """P-06-T19: a citation whose source is not a withdrawn version: its quote, value and box
    never reach anyone once the client withdrew the file (ADR-162 §4)."""
    return or_(
        Citation.source_type != "evidence_version",
        ~(
            select(EvidenceWithdrawal.evidence_version_id)
            .where(EvidenceWithdrawal.evidence_version_id == Citation.source_id)
            .exists()
        ),
    )


async def is_withdrawn(session: AsyncSession, version_id: UUID) -> bool:
    found = await session.execute(
        select(EvidenceWithdrawal.evidence_version_id).where(
            EvidenceWithdrawal.evidence_version_id == version_id
        )
    )
    return found.scalar_one_or_none() is not None


async def get_version(session: AsyncSession, version_id: UUID) -> EvidenceVersion | None:
    """The version, unless the client withdrew it (P-06-T19)."""
    return (
        await session.execute(
            select(EvidenceVersion).where(EvidenceVersion.id == version_id, not_withdrawn())
        )
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
                    not_withdrawn(),
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
                select(EvidenceVersion).where(
                    EvidenceVersion.engagement_id == engagement_id, seen, not_withdrawn()
                )
            )
        )
        .scalars()
        .all()
    )
    # P-01-T13: decided means an effective decision (the highest row is odd, not an undo).
    decided = set(
        (
            await session.execute(
                select(ReviewDecision.evidence_version_id)
                .where(
                    ReviewDecision.engagement_id == engagement_id,
                    visible(ctx, "review.read", ReviewDecision.engagement_id),
                )
                .group_by(ReviewDecision.evidence_version_id)
                .having(func.max(ReviewDecision.decision_seq) % 2 == 1)
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


async def latest_decision_row(session: AsyncSession, version_id: UUID) -> ReviewDecision | None:
    """The version's highest-numbered row (a decision or an undo), if any (P-01-T13)."""
    return (
        await session.execute(
            select(ReviewDecision)
            .where(ReviewDecision.evidence_version_id == version_id)
            .order_by(ReviewDecision.decision_seq.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def decision_for(session: AsyncSession, version_id: UUID) -> ReviewDecision | None:
    """The version's effective decision: its highest-numbered row when that is not an undo."""
    latest = await latest_decision_row(session, version_id)
    return latest if latest is not None and latest.decision != "undone" else None


async def decision_by_id(session: AsyncSession, decision_id: UUID) -> ReviewDecision | None:
    return (
        await session.execute(select(ReviewDecision).where(ReviewDecision.id == decision_id))
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
        .where(
            EvidenceVersion.id.in_(version_ids),
            EvidenceVersion.method == "uploaded",
            not_withdrawn(),
        )
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
        .where(
            EvidenceVersion.id.in_(version_ids),
            EvidenceVersion.fingerprint == fingerprint,
            not_withdrawn(),
        )
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
    later = aliased(ReviewDecision)
    newest_seq = (
        select(func.max(later.decision_seq))
        .where(later.evidence_version_id == EvidenceVersion.id)
        .scalar_subquery()
    )
    rows = await session.execute(
        select(EvidenceVersion, EvidenceItem, ReviewDecision)
        .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
        .outerjoin(
            ReviewDecision,
            (ReviewDecision.evidence_version_id == EvidenceVersion.id)
            & (ReviewDecision.request_item_id == request_item_id)
            # P-01-T13: the effective decision only (an undone one is no decision).
            & (ReviewDecision.decision_seq == newest_seq)
            & (ReviewDecision.decision != "undone"),
        )
        .where(EvidenceVersion.id.in_(version_ids), not_withdrawn())
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
            not_withdrawn(),
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


async def return_to_waiting(session: AsyncSession, version_id: UUID) -> UUID | None:
    """R-01 Story 2.2: the inbox file a voided rule link assigned to `version_id` waits for a
    person again (status, assignment and decision cleared; `sort_outcome` keeps what the sort
    did). None when no file was assigned to it."""
    return (
        await session.execute(
            update(InboxFile)
            .where(InboxFile.assigned_version_id == version_id, InboxFile.status == "assigned")
            .values(
                status="waiting",
                assigned_item_id=None,
                assigned_version_id=None,
                decided_by=None,
                decided_at=None,
            )
            .returning(InboxFile.id)
        )
    ).scalar_one_or_none()


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


async def newest_extraction(
    session: AsyncSession,
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
) -> UploadExtraction | None:
    """TASK-333: the upload's newest extraction by any extractor version. Readers use this: an
    extraction made by an earlier version stays valid data after the extractor improves (bumping
    the version must not make earlier uploads look empty)."""
    source = (
        UploadExtraction.evidence_version_id == evidence_version_id
        if evidence_version_id is not None
        else UploadExtraction.inbox_file_id == inbox_file_id
    )
    return (
        await session.execute(
            select(UploadExtraction)
            .where(source)
            .order_by(UploadExtraction.created_at.desc(), UploadExtraction.id.desc())
            .limit(1)
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
                # 0109 (P-03-T04): the one-per-source index includes the derivation.
                index_elements=["tenant_id", where, "extractor_version", "derivation_id"],
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
                not_withdrawn(),
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


async def preview_for(
    session: AsyncSession,
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
    renderer_version: str,
) -> UploadPreview | None:
    """SPEC-029 (TASK-056): the upload's preview by this renderer version, if made."""
    source = (
        UploadPreview.evidence_version_id == evidence_version_id
        if evidence_version_id is not None
        else UploadPreview.inbox_file_id == inbox_file_id
    )
    return (
        await session.execute(
            select(UploadPreview).where(source, UploadPreview.renderer_version == renderer_version)
        )
    ).scalar_one_or_none()


async def insert_preview(session: AsyncSession, **values: object) -> UploadPreview | None:
    """The new preview, or None when this source already has one by this renderer version."""
    by_version = values.get("evidence_version_id") is not None
    where = "evidence_version_id" if by_version else "inbox_file_id"
    present = (
        UploadPreview.evidence_version_id.is_not(None)
        if by_version
        else UploadPreview.inbox_file_id.is_not(None)
    )
    return (
        await session.execute(
            pg_insert(UploadPreview)
            .values(**values)
            .on_conflict_do_nothing(
                # 0109 (P-03-T04): the one-per-source index includes the derivation.
                index_elements=["tenant_id", where, "renderer_version", "derivation_id"],
                index_where=present,
            )
            .returning(UploadPreview)
        )
    ).scalar_one_or_none()


async def insert_preview_pages(session: AsyncSession, rows: Sequence[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(UploadPreviewPage).values(list(rows)))


async def preview_page(
    session: AsyncSession, preview_id: UUID, page_no: int
) -> UploadPreviewPage | None:
    return (
        await session.execute(
            select(UploadPreviewPage).where(
                UploadPreviewPage.preview_id == preview_id, UploadPreviewPage.page_no == page_no
            )
        )
    ).scalar_one_or_none()


async def problem_counts(
    session: AsyncSession, ctx: AuthContext, version_ids: Sequence[UUID], *, client_only: bool
) -> dict[UUID, int]:
    """SPEC-029 (TASK-057 D1): per version, the problem checks of its latest run (the newest
    checker version and kind), for a caller who has listed those versions."""
    if not version_ids:
        return {}
    rows = (
        await session.execute(
            select(
                UploadCheck.evidence_version_id,
                UploadCheck.checker_version,
                UploadCheck.document_kind,
                UploadCheck.outcome,
                UploadCheck.audience,
                UploadCheck.created_at,
            ).where(
                UploadCheck.evidence_version_id.in_(version_ids),
                visible(ctx, "evidence.read", UploadCheck.engagement_id),
            )
        )
    ).all()
    latest: dict[UUID, tuple[datetime, str, str | None]] = {}
    for row in rows:
        seen = latest.get(row.evidence_version_id)
        if seen is None or row.created_at > seen[0]:
            latest[row.evidence_version_id] = (
                row.created_at,
                row.checker_version,
                row.document_kind,
            )
    counts: dict[UUID, int] = {}
    for row in rows:
        _, version, kind = latest[row.evidence_version_id]
        if (row.checker_version, row.document_kind) != (version, kind) or row.outcome != "problem":
            continue
        if client_only and row.audience != "client":
            continue
        counts[row.evidence_version_id] = counts.get(row.evidence_version_id, 0) + 1
    return counts


async def stale_pdf_uploads(
    session: AsyncSession, extractor_version: str, limit: int
) -> list[tuple[str, UUID]]:
    """TASK-344: PDF uploads and inbox files with no extraction by this version, oldest first
    (LIST_EXEMPT: for the system re-read tool, never for a person)."""
    has_version = (
        select(UploadExtraction.id)
        .where(UploadExtraction.extractor_version == extractor_version)
        .correlate_except(UploadExtraction)
    )
    versions = (
        (
            await session.execute(
                select(EvidenceVersion.id)
                .where(
                    EvidenceVersion.media_type == "application/pdf",
                    ~has_version.where(
                        UploadExtraction.evidence_version_id == EvidenceVersion.id
                    ).exists(),
                    not_withdrawn(),
                )
                .order_by(EvidenceVersion.created_at)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    inbox = (
        (
            await session.execute(
                select(InboxFile.id)
                .where(
                    InboxFile.media_type == "application/pdf",
                    ~has_version.where(UploadExtraction.inbox_file_id == InboxFile.id).exists(),
                )
                .order_by(InboxFile.created_at)
                .limit(max(limit - len(versions), 0))
            )
        )
        .scalars()
        .all()
    )
    return [("version", v) for v in versions] + [("inbox", i) for i in inbox]


# --- The word layer (P-03-T05) and citations (P-03-T06) ----------------------------------------


async def pages_of(
    session: AsyncSession,
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
    extractor_version: str,
) -> Sequence[EvidencePage]:
    """A source's word-layer pages by this extractor version, by page (none derived), for the
    system or a caller that authorised on the source (LIST_EXEMPT: one source's pages)."""
    source = (
        and_(
            EvidencePage.evidence_version_id == evidence_version_id,
            ~(
                select(EvidenceWithdrawal.evidence_version_id)
                .where(EvidenceWithdrawal.evidence_version_id == evidence_version_id)
                .exists()
            ),  # P-06-T19: a withdrawn version's word layer is never read
        )
        if evidence_version_id is not None
        else EvidencePage.inbox_file_id == inbox_file_id
    )
    return (
        (
            await session.execute(
                select(EvidencePage)
                .where(
                    source,
                    EvidencePage.derivation_id.is_(None),
                    EvidencePage.extractor_version == extractor_version,
                )
                .order_by(EvidencePage.page_no)
            )
        )
        .scalars()
        .all()
    )


async def insert_pages(session: AsyncSession, rows: Sequence[dict[str, object]]) -> int:
    """The pages written; a page a concurrent run already wrote is left alone."""
    if not rows:
        return 0
    added = await session.execute(
        pg_insert(EvidencePage)
        .values(list(rows))
        .on_conflict_do_nothing()
        .returning(EvidencePage.id)
    )
    return len(added.scalars().all())


async def sources_without_words(
    session: AsyncSession,
    extractor_version: str,
    *,
    after_version: UUID | None,
    after_inbox: UUID | None,
    limit: int,
) -> list[tuple[str, UUID]]:
    """P-03-T05: PDF versions, then inbox files, by id after the cursors, with no word layer by
    this version and an extraction that read them (LIST_EXEMPT: the system backfill only)."""
    readable = (
        select(UploadExtraction.id)
        .where(UploadExtraction.status != "unreadable")
        .correlate_except(UploadExtraction)
    )
    layered = (
        select(EvidencePage.id)
        .where(
            EvidencePage.extractor_version == extractor_version,
            EvidencePage.derivation_id.is_(None),
        )
        .correlate_except(EvidencePage)
    )
    version_query = select(EvidenceVersion.id).where(
        EvidenceVersion.media_type == "application/pdf",
        readable.where(UploadExtraction.evidence_version_id == EvidenceVersion.id).exists(),
        ~layered.where(EvidencePage.evidence_version_id == EvidenceVersion.id).exists(),
        not_withdrawn(),
    )
    if after_version is not None:
        version_query = version_query.where(EvidenceVersion.id > after_version)
    versions = (
        (await session.execute(version_query.order_by(EvidenceVersion.id).limit(limit)))
        .scalars()
        .all()
    )
    inbox_query = select(InboxFile.id).where(
        InboxFile.media_type == "application/pdf",
        readable.where(UploadExtraction.inbox_file_id == InboxFile.id).exists(),
        ~layered.where(EvidencePage.inbox_file_id == InboxFile.id).exists(),
    )
    if after_inbox is not None:
        inbox_query = inbox_query.where(InboxFile.id > after_inbox)
    inbox = (
        (
            await session.execute(
                inbox_query.order_by(InboxFile.id).limit(max(limit - len(versions), 0))
            )
        )
        .scalars()
        .all()
    )
    return [("version", v) for v in versions] + [("inbox", i) for i in inbox]


async def sources_without_masks(
    session: AsyncSession,
    renderer_version: str,
    *,
    after_version: UUID | None,
    after_inbox: UUID | None,
    limit: int,
) -> list[tuple[str, UUID]]:
    """P-03-T15: versions, then inbox files, by id after the cursors, that processing has
    extracted (any outcome) and that have no masked rendition by this renderer version
    (LIST_EXEMPT: the system backfill only). A withdrawn version is never listed."""
    extracted = select(UploadExtraction.id).correlate_except(UploadExtraction)
    masked = (
        select(UploadPreview.id)
        .where(
            UploadPreview.renderer_version == renderer_version,
            UploadPreview.mask_version.is_not(None),
            UploadPreview.derivation_id.is_(None),
        )
        .correlate_except(UploadPreview)
    )
    version_query = select(EvidenceVersion.id).where(
        extracted.where(UploadExtraction.evidence_version_id == EvidenceVersion.id).exists(),
        ~masked.where(UploadPreview.evidence_version_id == EvidenceVersion.id).exists(),
        not_withdrawn(),
    )
    if after_version is not None:
        version_query = version_query.where(EvidenceVersion.id > after_version)
    versions = (
        (await session.execute(version_query.order_by(EvidenceVersion.id).limit(limit)))
        .scalars()
        .all()
    )
    inbox_query = select(InboxFile.id).where(
        extracted.where(UploadExtraction.inbox_file_id == InboxFile.id).exists(),
        ~masked.where(UploadPreview.inbox_file_id == InboxFile.id).exists(),
    )
    if after_inbox is not None:
        inbox_query = inbox_query.where(InboxFile.id > after_inbox)
    inbox = (
        (
            await session.execute(
                inbox_query.order_by(InboxFile.id).limit(max(limit - len(versions), 0))
            )
        )
        .scalars()
        .all()
    )
    return [("version", v) for v in versions] + [("inbox", i) for i in inbox]


async def next_citation_n(session: AsyncSession, cited_from_type: str, cited_from_id: UUID) -> int:
    """The next position in an anchor's stack (1 for a new anchor)."""
    found = (
        await session.execute(
            select(func.max(Citation.n)).where(
                Citation.cited_from_type == cited_from_type,
                Citation.cited_from_id == cited_from_id,
            )
        )
    ).scalar_one_or_none()
    return int(found or 0) + 1


async def insert_citation(session: AsyncSession, values: dict[str, object]) -> UUID:
    return (
        await session.execute(insert(Citation).values(**values).returning(Citation.id))
    ).scalar_one()


async def decisions_for_screenings(
    session: AsyncSession, screening_result_ids: Sequence[UUID]
) -> Sequence[ReviewDecision]:
    """Oldest first (LIST_EXEMPT: for the run trace, after authorising on the engagement)."""
    if not screening_result_ids:
        return []
    undo = aliased(ReviewDecision)
    return (
        (
            await session.execute(
                select(ReviewDecision)
                .where(
                    ReviewDecision.screening_result_id.in_(screening_result_ids),
                    # P-01-T13: an undone decision is no decision on the proposal.
                    ~exists().where(
                        undo.tenant_id == ReviewDecision.tenant_id,
                        undo.undoes_decision_id == ReviewDecision.id,
                    ),
                )
                .order_by(ReviewDecision.created_at)
            )
        )
        .scalars()
        .all()
    )


# --- citation and viewer reads (P-03-T08, T09) -------------------------------------------------


async def get_citation(session: AsyncSession, citation_id: UUID) -> Citation | None:
    """One citation in the session's firm; the caller authorises on its engagement."""
    return await session.get(Citation, citation_id)


async def events_of(
    session: AsyncSession, citation_ids: Sequence[UUID]
) -> Sequence[CitationEvent]:
    """The citations' events, oldest first (LIST_EXEMPT: of rows the caller already read
    through `visible()` or authorised on)."""
    if not citation_ids:
        return []
    return (
        (
            await session.execute(
                select(CitationEvent)
                .where(CitationEvent.citation_id.in_(list(citation_ids)))
                .order_by(CitationEvent.at, CitationEvent.id)
            )
        )
        .scalars()
        .all()
    )


async def pii_regions_of(
    session: AsyncSession,
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
    detector_version: str | None = None,
) -> Sequence[PiiRegion]:
    """A source's detected regions (none derived), by page; never their sealed values
    (LIST_EXEMPT: one source's regions, for a caller that authorised on it)."""
    source = (
        PiiRegion.evidence_version_id == evidence_version_id
        if evidence_version_id is not None
        else PiiRegion.inbox_file_id == inbox_file_id
    )
    return (
        (
            await session.execute(
                select(PiiRegion)
                .where(
                    source,
                    PiiRegion.derivation_id.is_(None),
                    # P-03-T15 review: only the regions of the current layer's scan, when named.
                    PiiRegion.detector_version == detector_version
                    if detector_version is not None
                    else true(),
                )
                .order_by(PiiRegion.page_no, PiiRegion.id)
            )
        )
        .scalars()
        .all()
    )


async def scanned_pages(
    session: AsyncSession,
    *,
    evidence_version_id: UUID | None = None,
    inbox_file_id: UUID | None = None,
    detector_version: str | None = None,
) -> set[int]:
    """The pages any PII scan of the source (none derived) recorded as scanned (LIST_EXEMPT:
    one source's scan runs, for a caller that authorised on it)."""
    source = (
        PiiScanRun.evidence_version_id == evidence_version_id
        if evidence_version_id is not None
        else PiiScanRun.inbox_file_id == inbox_file_id
    )
    rows = (
        await session.execute(
            select(PiiScanRun.pages_scanned).where(
                source,
                PiiScanRun.derivation_id.is_(None),
                PiiScanRun.detector_version == detector_version
                if detector_version is not None
                else true(),
            )
        )
    ).scalars()
    return {int(page) for pages in rows for page in pages}


async def preview_pages_of(session: AsyncSession, preview_id: UUID) -> Sequence[UploadPreviewPage]:
    """A preview's page images' rows, by page (LIST_EXEMPT: one preview's pages)."""
    return (
        (
            await session.execute(
                select(UploadPreviewPage)
                .where(UploadPreviewPage.preview_id == preview_id)
                .order_by(UploadPreviewPage.page_no)
            )
        )
        .scalars()
        .all()
    )


async def masked_preview_for(
    session: AsyncSession,
    evidence_version_id: UUID | None = None,
    *,
    inbox_file_id: UUID | None = None,
) -> UploadPreview | None:
    """The source's newest masked rendition (none derived): a preview with `mask_version` set
    (P-03-T09, T15). None until the masker has rendered it."""
    source = (
        UploadPreview.evidence_version_id == evidence_version_id
        if evidence_version_id is not None
        else UploadPreview.inbox_file_id == inbox_file_id
    )
    return (
        await session.execute(
            select(UploadPreview)
            .where(
                source,
                UploadPreview.derivation_id.is_(None),
                UploadPreview.mask_version.is_not(None),
            )
            .order_by(UploadPreview.created_at.desc(), UploadPreview.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def verified_citations_into(
    session: AsyncSession, ctx: AuthContext, version_id: UUID, match_ids: Sequence[str] | None
) -> Sequence[Citation]:
    """Verified citations whose source is the version, on engagements the caller may read the
    evidence of (`visible()`), oldest first, at most 200 (P-03-T09 regions)."""
    stmt = select(Citation).where(
        Citation.source_type == "evidence_version",
        Citation.source_id == version_id,
        Citation.verified.is_(True),
        Citation.match_id.is_not(None),
        visible(
            ctx, "evidence.read", cast(ColumnElement[UUID], Citation.engagement_id.expression)
        ),
        shown_citation(),
    )
    if match_ids is not None:
        stmt = stmt.where(Citation.match_id.in_(list(match_ids)))
    return (
        (await session.execute(stmt.order_by(Citation.created_at, Citation.id).limit(200)))
        .scalars()
        .all()
    )


async def verified_citations_of(
    session: AsyncSession, cited_from_type: str, cited_from_ids: Sequence[UUID]
) -> Sequence[tuple[UUID, UUID, str | None]]:
    """P-06-T20: the verified citations written for these anchors (id, anchor, ref), whose
    source the client has not withdrawn, in order. LIST_EXEMPT: keyed by anchors the caller
    composed from (the screening aggregate, a system caller) or authorised on."""
    if not cited_from_ids:
        return []
    rows = await session.execute(
        select(Citation.id, Citation.cited_from_id, Citation.cited_from_ref)
        .where(
            Citation.cited_from_type == cited_from_type,
            Citation.cited_from_id.in_(list(cited_from_ids)),
            Citation.verified.is_(True),
            shown_citation(),
        )
        .order_by(Citation.cited_from_id, Citation.n, Citation.id)
    )
    return [(r.id, r.cited_from_id, r.cited_from_ref) for r in rows.all()]


# --- The portal PBC read model (R-01-T07) --------------------------------------------------------


async def ever_accepted(session: AsyncSession, version_ids: Sequence[UUID]) -> frozenset[UUID]:
    """Which of these versions a person ever accepted (an `accept` row, undone or not, or a
    retained key): never withdrawable again (ADR-162 §8; DEC-298). LIST_EXEMPT: by id, for a
    caller that read them."""
    if not version_ids:
        return frozenset()
    accepted = await session.execute(
        select(ReviewDecision.evidence_version_id).where(
            ReviewDecision.evidence_version_id.in_(version_ids),
            ReviewDecision.decision == "accept",
        )
    )
    retained = await session.execute(
        select(EvidenceObjectKey.evidence_version_id).where(
            EvidenceObjectKey.evidence_version_id.in_(version_ids),
            EvidenceObjectKey.retained_at.is_not(None),
        )
    )
    return frozenset(accepted.scalars().all()) | frozenset(retained.scalars().all())


async def client_problem_codes(session: AsyncSession, version_id: UUID) -> list[str]:
    """The client-audience problem checks of the version's latest run (SPEC-029; DEC-58 e), by
    code, for a caller that read the version (LIST_EXEMPT)."""
    rows = (
        await session.execute(
            select(
                UploadCheck.check_code,
                UploadCheck.checker_version,
                UploadCheck.document_kind,
                UploadCheck.outcome,
                UploadCheck.audience,
                UploadCheck.created_at,
            ).where(UploadCheck.evidence_version_id == version_id)
        )
    ).all()
    if not rows:
        return []
    newest = max(rows, key=lambda r: r.created_at)
    return sorted(
        {
            r.check_code
            for r in rows
            if (r.checker_version, r.document_kind)
            == (newest.checker_version, newest.document_kind)
            and r.outcome == "problem"
            and r.audience == "client"
        }
    )


# --- moved and broken detection, relink (P-03-T12) ---------------------------------------------


async def earlier_versions(
    session: AsyncSession, item_id: UUID, version_no: int
) -> Sequence[UUID]:
    """The item's versions before `version_no` (withdrawn ones included: their citations are
    broken, not moved, and the caller tells them apart). LIST_EXEMPT: the system detector."""
    return (
        (
            await session.execute(
                select(EvidenceVersion.id).where(
                    EvidenceVersion.evidence_item_id == item_id,
                    EvidenceVersion.version_no < version_no,
                )
            )
        )
        .scalars()
        .all()
    )


async def newest_live_successor(
    session: AsyncSession, item_id: UUID, version_no: int
) -> EvidenceVersion | None:
    """The item's newest version after `version_no` that the client did not withdraw."""
    return (
        await session.execute(
            select(EvidenceVersion)
            .where(
                EvidenceVersion.evidence_item_id == item_id,
                EvidenceVersion.version_no > version_no,
                not_withdrawn(),
            )
            .order_by(EvidenceVersion.version_no.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def citations_on(
    session: AsyncSession,
    source_type: str,
    source_ids: Sequence[UUID],
    *,
    source_version: str | None = None,
) -> Sequence[Citation]:
    """Every citation whose source is one of these (LIST_EXEMPT: the system detector, and an
    owner's `mark_sources_superseded` in its own unit of work)."""
    if not source_ids:
        return []
    stmt = select(Citation).where(
        Citation.source_type == source_type, Citation.source_id.in_(list(source_ids))
    )
    if source_version is not None:
        stmt = stmt.where(Citation.source_version == source_version)
    return (await session.execute(stmt.order_by(Citation.id))).scalars().all()


async def insert_citation_events(
    session: AsyncSession, rows: Sequence[dict[str, object]]
) -> list[UUID]:
    """The citations that got a new event; a `moved` or `broken` event a run already wrote for
    the same cause is left alone (`citation_events_once_per_cause`, 0152)."""
    if not rows:
        return []
    added = await session.execute(
        pg_insert(CitationEvent)
        .values(list(rows))
        .on_conflict_do_nothing()
        .returning(CitationEvent.citation_id)
    )
    return list(added.scalars().all())


async def lock_citation(session: AsyncSession, citation_id: UUID) -> None:
    """Serialise relinks of one citation for the rest of the transaction (citations are
    insert-only: no row lock)."""
    await session.execute(_LOCK_ITEM, {"space": _CITATION_LOCK_SPACE, "item": str(citation_id)})


_CITATION_LOCK_SPACE = 9_005


# --- PII scan (P-03-T13) -------------------------------------------------------------------------

# `pii_regions` with its sealed value: the mapped model leaves `value_sealed` out on purpose (only
# the reveal service reads it), so the detector's insert names the table's columns here.
_PII_REGION_ROWS = table(
    "pii_regions",
    column("id", PgUUID(as_uuid=True)),
    column("tenant_id", PgUUID(as_uuid=True)),
    column("evidence_version_id", PgUUID(as_uuid=True)),
    column("inbox_file_id", PgUUID(as_uuid=True)),
    column("derivation_id", PgUUID(as_uuid=True)),
    column("page_no", Integer()),
    column("bbox", ARRAY(Numeric(10, 2))),
    column("kind", Text()),
    column("value_sealed", LargeBinary()),
    column("last4", Text()),
    column("label_anchored", Boolean()),
    column("detector_version", Text()),
)


async def insert_pii_regions(session: AsyncSession, rows: Sequence[dict[str, object]]) -> None:
    if rows:
        await session.execute(insert(_PII_REGION_ROWS).values(list(rows)))


async def scan_run_for(
    session: AsyncSession,
    *,
    evidence_version_id: UUID | None,
    inbox_file_id: UUID | None,
    detector_version: str,
) -> PiiScanRun | None:
    """The source's scan run by this detector version (none derived), if any."""
    return (
        await session.execute(
            select(PiiScanRun).where(
                PiiScanRun.evidence_version_id == evidence_version_id
                if evidence_version_id is not None
                else PiiScanRun.inbox_file_id == inbox_file_id,
                PiiScanRun.derivation_id.is_(None),
                PiiScanRun.detector_version == detector_version,
            )
        )
    ).scalar_one_or_none()


async def insert_scan_run(session: AsyncSession, **values: object) -> bool:
    """Whether this run was the first (a concurrent one that got there first wins)."""
    found = await session.execute(
        pg_insert(PiiScanRun).values(**values).on_conflict_do_nothing().returning(PiiScanRun.id)
    )
    return found.scalar_one_or_none() is not None


# --- portal drops (R-01-T09) ---------------------------------------------------------------------


async def drop_by_key(
    session: AsyncSession, batch_id: UUID, key: str, dropped_by: UUID
) -> InboxFile | None:
    """The drop this person's (batch, idempotency key) already made, if any."""
    return (
        await session.execute(
            select(InboxFile).where(
                InboxFile.channel == "portal_drop",
                InboxFile.drop_batch_id == batch_id,
                InboxFile.drop_key == key,
                InboxFile.uploaded_by == dropped_by,
            )
        )
    ).scalar_one_or_none()


async def drops_of_batch(
    session: AsyncSession, batch_id: UUID, dropped_by: UUID
) -> Sequence[InboxFile]:
    """One person's own files in one drop batch, in order (LIST_EXEMPT: the dropper's own rows,
    re-authorised on the binder after reading)."""
    return (
        (
            await session.execute(
                select(InboxFile)
                .where(
                    InboxFile.channel == "portal_drop",
                    InboxFile.drop_batch_id == batch_id,
                    InboxFile.uploaded_by == dropped_by,
                )
                .order_by(InboxFile.created_at, InboxFile.id)
            )
        )
        .scalars()
        .all()
    )


async def set_sort_outcome(session: AsyncSession, file_id: UUID, outcome: str) -> None:
    """A drop's sort outcome, once (from NULL; the 0153 trigger refuses any other change)."""
    await session.execute(
        update(InboxFile)
        .where(InboxFile.id == file_id, InboxFile.sort_outcome.is_(None))
        .values(sort_outcome=outcome)
    )
