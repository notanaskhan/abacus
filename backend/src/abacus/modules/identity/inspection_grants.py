"""Inspector access (Q-05-T16 part 1; SPEC-711 AC-7, AC-8; OQ-6; DEC-5825). PROTECTED (red).

An inspection's planning issues each inspector a grant per covered engagement: read-only (the
actions in `INSPECTION_READS` only), until the inspection concludes or its due date + 30 days,
whichever is first, revocable. `authorise` treats a live grant as the `inspector` relationship for
those actions only; `visible()` lists the granted engagements' rows for them. Walls are checked
before any relationship, so a walled inspector sees nothing (DEC-43). The agent, the system and
support never hold a grant.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import ColumnElement, and_, column, or_, select, table, text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow

INSPECTOR: Final = "inspector"
GRACE: Final = timedelta(days=30)
# Read-only: the archive, its documents and workpapers, the activity log (ADM-12 e, f).
INSPECTION_READS: Final = frozenset(
    {
        "engagement.read",
        "evidence.read",
        "workpaper.read",
        "audit_trail.read",
        "archive.read",
        "review.read",
        "issue.read",
        "sign_off.read",
        "procedure.read",
        "document.read",
    }
)

_grants = table(
    "inspection_access_grants",
    column("engagement_id"),
    column("inspector_user_id"),
    column("expires_at"),
    column("revoked_at"),
)


def expiry(concludes_on: datetime | None, due_at: datetime) -> datetime:
    """At the conclusion, or the due date + 30 days, whichever comes first."""
    cap = due_at + GRACE
    return cap if concludes_on is None else min(concludes_on, cap)


async def issue(
    tx: UnitOfWork,
    *,
    tenant_id: UUID,
    inspection_id: UUID,
    inspector_user_id: UUID,
    engagement_ids: Sequence[UUID],
    granted_by: UUID,
    expires_at: datetime,
) -> int:
    """In the planner's unit of work (practice's inspection planning, Q-05-T18)."""
    n = 0
    for engagement_id in sorted(set(engagement_ids)):
        found = await tx.session.scalar(
            text(
                "INSERT INTO inspection_access_grants (tenant_id, inspection_id, "
                "inspector_user_id, "
                "engagement_id, granted_by, expires_at) VALUES (:t, :i, :u, :e, :by, :x) "
                "ON CONFLICT (tenant_id, inspection_id, inspector_user_id, engagement_id) DO "
                "NOTHING "
                "RETURNING id"
            ),
            {
                "t": tenant_id,
                "i": inspection_id,
                "u": inspector_user_id,
                "e": engagement_id,
                "by": granted_by,
                "x": expires_at,
            },
        )
        if found is not None:
            n += 1
            tx.record(
                "inspection_grant.issued",
                target=Target("inspection_access_grant", found),
                after=Ref(engagement_id=engagement_id),
            )
    return n


async def revoke_for_inspection(tx: UnitOfWork, inspection_id: UUID, by: str) -> int:
    """At conclusion (or a planner's revoke): every live grant of the inspection ends now."""
    rows = list(
        await tx.session.scalars(
            text(
                "UPDATE inspection_access_grants SET revoked_at = clock_timestamp(), revoked_by = "
                ":by WHERE inspection_id = :i AND revoked_at IS NULL RETURNING id"
            ),
            {"i": inspection_id, "by": by},
        )
    )
    for grant_id in rows:
        tx.record("inspection_grant.revoked", target=Target("inspection_access_grant", grant_id))
    return len(rows)


async def sweep(tenant: TenantContext) -> int:
    """The nightly sweep: grants past their expiry are revoked (`system:sweep`)."""
    async with uow(tenant) as tx:
        rows = list(
            await tx.session.scalars(
                text(
                    "UPDATE inspection_access_grants SET revoked_at = clock_timestamp(), "
                    "revoked_by = 'system:sweep' WHERE revoked_at IS NULL AND expires_at <= "
                    "clock_timestamp() RETURNING id"
                )
            )
        )
        for grant_id in rows:
            tx.record(
                "inspection_grant.expired", target=Target("inspection_access_grant", grant_id)
            )
    return len(rows)


async def holds_grant(
    session: AsyncSession, user_id: UUID, engagement_id: UUID, at: datetime | None = None
) -> bool:
    found = await session.scalar(
        text(
            "SELECT 1 FROM inspection_access_grants WHERE inspector_user_id = :u AND "
            "engagement_id = :e AND revoked_at IS NULL AND expires_at > :at LIMIT 1"
        ),
        {"u": user_id, "e": engagement_id, "at": at or system_now()},
    )
    return found is not None


async def inspector_of(
    tenant: TenantContext, user_id: UUID, engagement_id: UUID, action: str
) -> bool:
    """`authorise`'s relationship check: a live grant, for a read in `INSPECTION_READS`."""
    if action not in INSPECTION_READS:
        return False
    async with tenant_session(tenant) as session:
        return await holds_grant(session, user_id, engagement_id)


def inspector_reach(
    user_id: UUID, action: str, engagement_id: object
) -> ColumnElement[bool] | None:
    """`visible()`'s clause: the engagements a live grant covers, for an inspection read."""
    if action not in INSPECTION_READS:
        return None
    granted = select(_grants.c.engagement_id).where(
        and_(
            _grants.c.inspector_user_id == user_id,
            _grants.c.revoked_at.is_(None),
            _grants.c.expires_at > text("clock_timestamp()"),
        )
    )
    return or_(engagement_id.in_(granted))  # type: ignore[attr-defined] -- a narrower type than the declared one


__all__ = [
    "GRACE", "INSPECTION_READS", "INSPECTOR", "expiry", "holds_grant", "inspector_of",
    "inspector_reach", "issue", "revoke_for_inspection", "sweep",
]  # fmt: skip
