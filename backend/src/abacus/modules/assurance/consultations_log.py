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

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import column, func, select, table, text

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.assurance.events import ConsultationDifferenceRecorded
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    allowed_actions,
    authorise,
    quality_partners,
    team_of,
    visible,
)

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
    query: Any,  # noqa: ANN401 # Any: a Select over the lightweight consultations table
    *,
    engagement_id: UUID | None,
    consultee: UUID | None,
    year: int | None,
) -> Any:  # noqa: ANN401 # Any: the same Select, filtered
    out = query.where(visible(ctx, "consultation.read", cast(object, _C.c.engagement_id)))  # type: ignore[arg-type]  # a lightweight column
    if engagement_id is not None:
        out = out.where(_C.c.engagement_id == engagement_id)
    if consultee is not None:
        out = out.where(_C.c.consulted_with_user_id == consultee)
    if year is not None:
        out = out.where(func.extract("year", _C.c.created_at) == year)
    return out


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
        found = await session.execute(rows_q.order_by(_C.c.created_at, _C.c.ref))
        rows = [tuple(r) for r in found.all()]
        counted = [tuple(r) for r in (await session.execute(counts_q)).all()]
        counts = {str(r[0]): int(cast(int, r[1])) for r in counted}
    return ConsultationList(
        tuple(
            ConsultationRow(
                cast(UUID, r[0]),
                str(r[1]),
                cast(UUID | None, r[2]),
                str(r[3]),
                cast(UUID, r[4]),
                cast(UUID, r[5]),
                cast(datetime, r[6]),
            )
            for r in rows
        ),
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
        await engagement_resource_of(ctx.tenant, engagement_id)
        if engagement_id is not None
        else Resource.firm(ctx.tenant_id)
    )
    await authorise(ctx, action, resource)
    return status


# 0644's CHECK ties `concluded` to a conclusion: reopening clears it (and the implementation) and
# the audit event keeps the prior conclusion's hash (S51 partials, TASK-8729).
_REOPEN = text(
    "UPDATE consultations c SET status = 'open', conclusion_sealed = NULL, concluded_at = NULL, "
    "implemented = false, implemented_reference = NULL, reopened_at = clock_timestamp() "
    "FROM (SELECT id, conclusion_sealed FROM consultations WHERE id = :id FOR UPDATE) prior "
    "WHERE c.id = prior.id AND c.status = 'concluded' RETURNING prior.conclusion_sealed"
)


_CONSULTEE = text("SELECT consulted_with_user_id FROM consultations WHERE id = :id")


async def reopen(ctx: AuthContext, consultation_id: UUID) -> None:
    """The consultee or the QM owner only (AUD-28 g); the matrix's other roles may not."""
    if await _authorised(ctx, "consultation.reopen", consultation_id) != "concluded":
        raise ConsultationNotConcluded(facts={"consultation_id": str(consultation_id)})
    async with tenant_session(ctx.tenant) as session:
        consultee = await session.scalar(_CONSULTEE, {"id": consultation_id})
    if consultee != ctx.user_id:
        # The QM owner is who may resolve a difference here (the matrix's QM-only action).
        engagement_id, _ = await _consultation(ctx.tenant, consultation_id)
        resource = (
            await engagement_resource_of(ctx.tenant, engagement_id)
            if engagement_id is not None
            else Resource.firm(ctx.tenant_id)
        )
        if "consultation.resolve_difference" not in await allowed_actions(
            ctx, resource, ("consultation.resolve_difference",)
        ):
            raise Forbidden("consultation.reopen", "relationship")
    async with uow(ctx.tenant) as tx:
        prior = await tx.session.scalar(_REOPEN, {"id": consultation_id})
        if prior is None:
            raise ConsultationNotConcluded(facts={"consultation_id": str(consultation_id)})
        tx.record(
            "consultation.reopened",
            target=Target(TARGET, consultation_id),
            before=Ref(conclusion=hashlib.sha256(cast(bytes, prior)).hexdigest()),
        )


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
    engagement_id, _ = await _consultation(ctx.tenant, consultation_id)
    team = [] if engagement_id is None else await team_of(ctx.tenant_id, engagement_id)
    if (ctx.user_id, role) not in {(u, str(r)) for u, r in team}:
        # the position is the person's own, on that engagement, in the role they hold there
        raise Forbidden("consultation.record_position", "role")
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
        if not agrees:
            tx.emit(
                ConsultationDifferenceRecorded(
                    consultation_id=consultation_id,
                    by_user=ctx.user_id,
                    recipient_user_ids=await quality_partners(ctx.tenant_id),
                )
            )


class NoDifferenceToResolve(DomainConflict):
    code = "no_difference_to_resolve"


_DIFFERENCE_OPEN = text(
    "SELECT EXISTS (SELECT 1 FROM consultation_positions p WHERE p.consultation_id = :c "
    "AND NOT p.agrees) AND NOT EXISTS (SELECT 1 FROM consultation_resolutions r "
    "WHERE r.consultation_id = :c)"
)


async def resolve_difference(ctx: AuthContext, consultation_id: UUID, *, resolution: str) -> None:
    """The QM owner (firm role; the engagement's walls apply) resolves a recorded difference
    once; 409 `no_difference_to_resolve` when no position disagrees or it is already resolved."""
    await _authorised(ctx, "consultation.resolve_difference", consultation_id)
    sealed = await seal(ctx.tenant_id, resolution.strip().encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("SELECT id FROM consultations WHERE id = :c FOR UPDATE"), {"c": consultation_id}
        )
        if not await tx.session.scalar(_DIFFERENCE_OPEN, {"c": consultation_id}):
            raise NoDifferenceToResolve(facts={"consultation_id": str(consultation_id)})
        await tx.session.execute(
            text(
                "INSERT INTO consultation_resolutions (tenant_id, consultation_id, "
                "resolution_sealed, resolved_by) VALUES (:t, :c, :s, :u)"
            ),
            {"t": ctx.tenant_id, "c": consultation_id, "s": sealed, "u": ctx.user_id},
        )
        tx.record("consultation.difference_resolved", target=Target(TARGET, consultation_id))


@dataclass(frozen=True)
class Position:
    role: str
    agrees: bool
    position: str
    recorded_by: UUID
    at: datetime


@dataclass(frozen=True)
class Resolution:
    resolution: str
    resolved_by: UUID
    at: datetime
    before_release: bool


@dataclass(frozen=True)
class LinkRow:
    kind: str
    target_id: UUID
    linked_by: UUID
    at: datetime


@dataclass(frozen=True)
class ConsultationDetail:
    consultation_id: UUID
    work_item_id: UUID | None
    facts: str | None
    consulted_role: str | None
    implemented: bool
    implemented_reference: str | None
    reopened_at: datetime | None
    links: tuple[LinkRow, ...]
    positions: tuple[Position, ...]
    resolution: Resolution | None


_DETAIL = text(
    "SELECT work_item_id, facts_sealed, consulted_role, implemented, implemented_reference, "
    "reopened_at, consulted_with_user_id FROM consultations WHERE id = :id"
)
_LINKS = text(
    "SELECT target_kind, target_id, linked_by, at FROM consultation_links "
    "WHERE consultation_id = :id ORDER BY at, target_kind"
)
_POSITIONS = text(
    "SELECT role, agrees, position_sealed, recorded_by, at FROM consultation_positions "
    "WHERE consultation_id = :id ORDER BY at"
)
_RESOLUTION = text(
    "SELECT r.resolution_sealed, r.resolved_by, r.at, (SELECT min(rr.released_at) FROM "
    "report_releases rr WHERE rr.work_item_id = c.work_item_id) AS released_at "
    "FROM consultation_resolutions r JOIN consultations c ON c.id = r.consultation_id "
    "WHERE r.consultation_id = :id"
)


async def _opened(ctx: AuthContext, sealed: object) -> str:
    return (await open_sealed(ctx.tenant_id, cast(bytes, sealed), _FINGERPRINT)).decode()


async def detail(ctx: AuthContext, consultation_id: UUID) -> ConsultationDetail:
    """AUD-28's detail beyond A-06's record: facts, implementation, links, positions and the
    resolution (`before_release` computed from `report_releases`, never typed), behind
    `consultation.read` on the engagement (walls: 404)."""
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_DETAIL, {"id": consultation_id})).first()
        if row is None:
            raise NotFound(TARGET)
        await _authorised(ctx, "consultation.read", consultation_id)
        links = [tuple(r) for r in (await session.execute(_LINKS, {"id": consultation_id}))]
        positions = [
            tuple(r) for r in (await session.execute(_POSITIONS, {"id": consultation_id}))
        ]
        resolved = (await session.execute(_RESOLUTION, {"id": consultation_id})).first()
    resolution = None
    if resolved is not None:
        released = cast(datetime | None, resolved[3])
        at = cast(datetime, resolved[2])
        resolution = Resolution(
            await _opened(ctx, resolved[0]),
            cast(UUID, resolved[1]),
            at,
            released is None or at < released,
        )
    return ConsultationDetail(
        consultation_id,
        cast(UUID | None, row[0]),
        None if row[1] is None else await _opened(ctx, row[1]),
        cast(str | None, row[2]),
        bool(row[3]),
        cast(str | None, row[4]),
        cast(datetime | None, row[5]),
        tuple(
            LinkRow(str(r[0]), cast(UUID, r[1]), cast(UUID, r[2]), cast(datetime, r[3]))
            for r in links
        ),
        tuple(
            [
                Position(
                    str(r[0]),
                    bool(r[1]),
                    await _opened(ctx, r[2]),
                    cast(UUID, r[3]),
                    cast(datetime, r[4]),
                )
                for r in positions
            ]
        ),
        resolution,
    )


async def open_count(ctx: AuthContext) -> int:
    """Q-05-T08's signal (ADM-11 tile): the open consultations the viewer may read, counted the
    way the log counts them (walled rows never count; DEC-43)."""
    return (await firm_log(ctx, status="open")).counts["open"]


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
    "ConsultationDetail",
    "ConsultationList",
    "ConsultationRow",
    "NoDifferenceToResolve",
    "attach",
    "detail",
    "firm_log",
    "open_count",
    "record_position",
    "reopen",
    "resolve_difference",
    "unresolved_differences",
]
