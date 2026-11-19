"""The firm's consultations log v2 (Q-05-T09; TASK-8716; SPEC-711 AC-11 to AC-14; DEC-5712).
Dark behind `audit.consultations_log` until the Oct 24 train (P-29), beside A-06's minimal record
(`consultations.py`, whose conclude stays the consultee's only).

- **Log** (`firm_log`): every consultation the person may read (`visible`, walls applied before
  counting), filtered by engagement, status, consultee and year, with counts by status computed
  over the same visible rows: a walled user gets no row and no count.
- **Reopen**, **link** (insert-only), **record a position** (EP or EQR; insert-only, human-only)
  and **resolve a difference** (the QM owner; insert-only, human-only).
- **Release blocker** (`unresolved_differences`): a work item's consultations where a recorded
  position disagrees and no resolution exists; assurance's release gate reads it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import Select, column, func, select, table, text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise, visible

TARGET: Final = "consultation"
_FINGERPRINT: Final = "assurance.consultation"
Status = Literal["open", "concluded"]

_C = table(
    "consultations",
    column("id"),
    column("engagement_id"),
    column("work_item_id"),
    column("ref"),
    column("status"),
    column("consulted_with_user_id"),
    column("raised_by"),
    column("created_at"),
    column("concluded_at"),
)


class ConsultationNotConcluded(DomainConflict):
    code = "consultation_not_concluded"


@dataclass(frozen=True)
class ConsultationRow:
    consultation_id: UUID
    ref: str
    engagement_id: UUID | None
    status: str
    consulted_with_user_id: UUID
    raised_by: UUID
    created_at: datetime


@dataclass(frozen=True)
class ConsultationList:
    rows: tuple[ConsultationRow, ...]
    counts: dict[str, int]


def _filtered(
    ctx: AuthContext,
    query: Select[tuple[object, ...]],
    *,
    engagement_id: UUID | None,
    consultee: UUID | None,
    year: int | None,
) -> Select[tuple[object, ...]]:
    query = query.where(visible(ctx, "consultation.read", cast(object, _C.c.engagement_id)))  # type: ignore[arg-type]  # a lightweight column
    if engagement_id is not None:
        query = query.where(_C.c.engagement_id == engagement_id)
    if consultee is not None:
        query = query.where(_C.c.consulted_with_user_id == consultee)
    if year is not None:
        query = query.where(func.extract("year", _C.c.created_at) == year)
    return query


async def firm_log(
    ctx: AuthContext,
    *,
    engagement_id: UUID | None = None,
    status: Status | None = None,
    consultee: UUID | None = None,
    year: int | None = None,
) -> ConsultationList:
    rows_q = _filtered(
        ctx,
        select(
            _C.c.id, _C.c.ref, _C.c.engagement_id, _C.c.status, _C.c.consulted_with_user_id,
            _C.c.raised_by, _C.c.created_at,
        ),
        engagement_id=engagement_id, consultee=consultee, year=year,
    )  # fmt: skip
    if status is not None:
        rows_q = rows_q.where(_C.c.status == status)
    counts_q = _filtered(
        ctx,
        select(_C.c.status, func.count()).group_by(_C.c.status),
        engagement_id=engagement_id, consultee=consultee, year=year,
    )  # fmt: skip
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(rows_q.order_by(_C.c.created_at, _C.c.ref))).all()
        counts = {str(s): int(n) for s, n in (await session.execute(counts_q)).all()}
    return ConsultationList(
        tuple(ConsultationRow(r[0], str(r[1]), r[2], str(r[3]), r[4], r[5], r[6]) for r in rows),
        {"open": counts.get("open", 0), "concluded": counts.get("concluded", 0)},
    )


async def _consultation(tenant: TenantContext, consultation_id: UUID) -> tuple[UUID | None, str]:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                select(_C.c.engagement_id, _C.c.status).where(_C.c.id == consultation_id)
            )
        ).first()
    if row is None:
        raise NotFound(TARGET)
    return row[0], str(row[1])


async def _authorised(ctx: AuthContext, action: str, consultation_id: UUID) -> str:
    engagement_id, status = await _consultation(ctx.tenant, consultation_id)
    resource = (
        Resource.engagement(ctx.tenant_id, engagement_id)
        if engagement_id is not None
        else Resource.firm(ctx.tenant_id)
    )
    await authorise(ctx, action, resource)
    return status


_REOPEN = text(
    "UPDATE consultations SET status = 'open', reopened_at = clock_timestamp() "
    "WHERE id = :id AND status = 'concluded' RETURNING id"
)


async def reopen(ctx: AuthContext, consultation_id: UUID) -> None:
    if await _authorised(ctx, "consultation.reopen", consultation_id) != "concluded":
        raise ConsultationNotConcluded(facts={"consultation_id": str(consultation_id)})
    async with uow(ctx.tenant) as tx:
        if await tx.session.scalar(_REOPEN, {"id": consultation_id}) is None:
            raise ConsultationNotConcluded(facts={"consultation_id": str(consultation_id)})
        tx.record("consultation.reopened", target=Target(TARGET, consultation_id))


async def attach(ctx: AuthContext, consultation_id: UUID, kind: str, target_id: UUID) -> None:
    await _authorised(ctx, "consultation.link", consultation_id)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO consultation_links (tenant_id, consultation_id, target_kind, "
                "target_id, linked_by) VALUES (:t, :c, :k, :x, :u) ON CONFLICT DO NOTHING"
            ),
            {
                "t": ctx.tenant_id,
                "c": consultation_id,
                "k": kind,
                "x": target_id,
                "u": ctx.user_id,
            },
        )
        tx.record("consultation.linked", target=Target(TARGET, consultation_id))


async def record_position(
    ctx: AuthContext, consultation_id: UUID, *, role: str, agrees: bool, position: str
) -> None:
    await _authorised(ctx, "consultation.record_position", consultation_id)
    sealed = await seal(ctx.tenant_id, position.strip().encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO consultation_positions (tenant_id, consultation_id, role, agrees, "
                "position_sealed, recorded_by) VALUES (:t, :c, :r, :a, :p, :u)"
            ),
            {"t": ctx.tenant_id, "c": consultation_id, "r": role, "a": agrees, "p": sealed,
             "u": ctx.user_id},
        )  # fmt: skip
        tx.record(
            "consultation.position_recorded",
            target=Target(TARGET, consultation_id),
            after=Ref(agrees=int(agrees)),
        )


async def resolve_difference(ctx: AuthContext, consultation_id: UUID, *, resolution: str) -> None:
    await authorise(ctx, "consultation.resolve_difference", Resource.firm(ctx.tenant_id))
    await _consultation(ctx.tenant, consultation_id)
    sealed = await seal(ctx.tenant_id, resolution.strip().encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO consultation_resolutions (tenant_id, consultation_id, "
                "resolution_sealed, resolved_by) VALUES (:t, :c, :s, :u)"
            ),
            {"t": ctx.tenant_id, "c": consultation_id, "s": sealed, "u": ctx.user_id},
        )
        tx.record("consultation.difference_resolved", target=Target(TARGET, consultation_id))


_UNRESOLVED = text(
    "SELECT c.ref FROM consultations c WHERE c.work_item_id = :w AND EXISTS ("
    "SELECT 1 FROM consultation_positions p WHERE p.consultation_id = c.id AND NOT p.agrees) "
    "AND NOT EXISTS (SELECT 1 FROM consultation_resolutions r WHERE r.consultation_id = c.id) "
    "ORDER BY c.ref"
)


async def unresolved_differences(tenant: TenantContext, work_item_id: UUID) -> list[str]:
    """The release blocker: consultations with a disagreeing position and no resolution."""
    async with tenant_session(tenant) as session:
        return [str(r) for r in await session.scalars(_UNRESOLVED, {"w": work_item_id})]


__all__ = [
    "ConsultationList",
    "ConsultationRow",
    "attach",
    "firm_log",
    "record_position",
    "reopen",
    "resolve_difference",
    "unresolved_differences",
]
