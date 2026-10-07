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
    ReviewAssignment,
    ReviewDecision,
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
