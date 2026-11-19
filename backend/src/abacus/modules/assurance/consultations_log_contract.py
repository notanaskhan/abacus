"""Consultations log v2 routes (Q-05-T09; S51 partials, TASK-8729; DEC-5723; SPEC-711 AC-11 to
AC-14; Q-05 §5). Screen AUD-28: the firm log (`/audits/consultations`), its detail, reopen, links,
an EP's or EQR's position on a difference of opinion and the QM owner's resolution. A-06's work
item routes (`findings_contract.py`) keep create and conclude, with the v2 fields.

Every route answers, in order: a client principal 404 (no portal route); `audit.consultations_log`
off 404; a human-only route refuses an agent, the platform or a support session 403 (INV-1); then
the service authorises on the consultation's engagement (walls 404, no hidden counts; DEC-43).

Classification (ADR-031): facts, positions and resolutions are `confidential` (attest work, not
TRI); ids, refs, roles and states are `internal`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import AUDIT_CONSULTATIONS_LOG
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    current_context,
    names_of,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Confidential = classified("confidential")
LinkKind = Literal["finding", "issue", "document", "workpaper", "post_issuance_case"]
PositionRole = Literal["engagement_partner", "eqr_reviewer"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class ConsultationLogRowOut(BaseModel):
    model_config = _cfg()

    consultation_id: Annotated[UUID, Internal]
    ref: Annotated[str, Field(max_length=10), Internal]
    engagement_id: Annotated[UUID | None, Internal]
    status: Annotated[Literal["open", "concluded"], Internal]
    consulted_with_user_id: Annotated[UUID, Internal]
    consulted_with_name: Annotated[str, Internal]
    raised_by_name: Annotated[str, Internal]
    created_at: Annotated[datetime, Internal]


class ConsultationCountsOut(BaseModel):
    model_config = _cfg()

    open: Annotated[int, Internal]
    concluded: Annotated[int, Internal]


class ConsultationLogOut(BaseModel):
    """AUD-28 a: the bands Open and Concluded, counted over the rows the reader may see."""

    model_config = _cfg()

    items: list[ConsultationLogRowOut]
    counts: ConsultationCountsOut


class ConsultationLinkOut(BaseModel):
    model_config = _cfg()

    kind: Annotated[LinkKind, Internal]
    target_id: Annotated[UUID, Internal]
    linked_by_name: Annotated[str, Internal]
    at: Annotated[datetime, Internal]


class ConsultationPositionOut(BaseModel):
    model_config = _cfg()

    role: Annotated[PositionRole, Internal]
    agrees: Annotated[bool, Internal]
    position: Annotated[str, Confidential]
    recorded_by_name: Annotated[str, Internal]
    at: Annotated[datetime, Internal]


class ConsultationResolutionOut(BaseModel):
    model_config = _cfg()

    resolution: Annotated[str, Confidential]
    resolved_by_name: Annotated[str, Internal]
    at: Annotated[datetime, Internal]
    before_release: Annotated[bool, Internal]


class ConsultationDetailOut(BaseModel):
    """AUD-28 a/b: what A-06's record does not carry."""

    model_config = _cfg()

    consultation_id: Annotated[UUID, Internal]
    facts: Annotated[str | None, Confidential]
    consulted_role: Annotated[Literal["partner", "specialist", "national"] | None, Internal]
    implemented: Annotated[bool, Internal]
    implemented_reference: Annotated[str | None, Field(max_length=200), Internal]
    reopened_at: Annotated[datetime | None, Internal]
    links: list[ConsultationLinkOut]
    positions: list[ConsultationPositionOut]
    resolution: ConsultationResolutionOut | None
    difference_unresolved: Annotated[bool, Internal]


class ConsultationLinkIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Annotated[LinkKind, Internal]
    target_id: Annotated[UUID, Internal]


class ConsultationPositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Annotated[PositionRole, Internal]
    agrees: Annotated[bool, Internal]
    position: Annotated[str, Field(min_length=1, max_length=4000), Confidential]


class ConsultationResolutionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resolution: Annotated[str, Field(min_length=1, max_length=4000), Confidential]


consultations_log_router = AbacusRouter(prefix="/v1", tags=["assurance"])
_ONE = "/consultations/{consultation_id}"


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, AUDIT_CONSULTATIONS_LOG):
        raise NotFound(AUDIT_CONSULTATIONS_LOG.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


async def _named(ids: set[UUID]) -> dict[UUID, str]:
    return await names_of(sorted(ids, key=str)) if ids else {}


@consultations_log_router.get(
    "/consultations", action="consultation.read", response_model=ConsultationLogOut
)
async def consultations_log_route(
    ctx: Ctx,
    engagement_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[Literal["open", "concluded"] | None, Query()] = None,
    consulted_with: Annotated[UUID | None, Query()] = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
) -> ConsultationLogOut:
    """AUD-28 a, d, e: the firm log; walled rows never show or count (DEC-43)."""
    await _on(ctx)
    from abacus.modules.assurance import consultations_log as log

    found = await log.firm_log(
        ctx, engagement_id=engagement_id, status=status, consultee=consulted_with, year=year
    )
    names = await _named(
        {r.consulted_with_user_id for r in found.rows} | {r.raised_by for r in found.rows}
    )
    return ConsultationLogOut(
        items=[
            ConsultationLogRowOut(
                consultation_id=r.consultation_id,
                ref=r.ref,
                engagement_id=r.engagement_id,
                status="concluded" if r.status == "concluded" else "open",
                consulted_with_user_id=r.consulted_with_user_id,
                consulted_with_name=names.get(r.consulted_with_user_id, "Former member"),
                raised_by_name=names.get(r.raised_by, "Former member"),
                created_at=r.created_at,
            )
            for r in found.rows
        ],
        counts=ConsultationCountsOut(
            open=found.counts["open"], concluded=found.counts["concluded"]
        ),
    )


async def _detail(ctx: AuthContext, consultation_id: UUID) -> ConsultationDetailOut:
    from abacus.modules.assurance import consultations_log as log

    d = await log.detail(ctx, consultation_id)
    names = await _named(
        {x.linked_by for x in d.links}
        | {p.recorded_by for p in d.positions}
        | ({d.resolution.resolved_by} if d.resolution else set())
    )
    disagree = any(not p.agrees for p in d.positions)
    return ConsultationDetailOut(
        consultation_id=d.consultation_id,
        facts=d.facts,
        consulted_role=d.consulted_role,  # type: ignore[arg-type]  # the column's CHECK (0985)
        implemented=d.implemented,
        implemented_reference=d.implemented_reference,
        reopened_at=d.reopened_at,
        links=[
            ConsultationLinkOut(
                kind=x.kind,  # type: ignore[arg-type]  # the column's CHECK (0983)
                target_id=x.target_id,
                linked_by_name=names.get(x.linked_by, "Former member"),
                at=x.at,
            )
            for x in d.links
        ],
        positions=[
            ConsultationPositionOut(
                role=p.role,  # type: ignore[arg-type]  # the column's CHECK (0983)
                agrees=p.agrees,
                position=p.position,
                recorded_by_name=names.get(p.recorded_by, "Former member"),
                at=p.at,
            )
            for p in d.positions
        ],
        resolution=None
        if d.resolution is None
        else ConsultationResolutionOut(
            resolution=d.resolution.resolution,
            resolved_by_name=names.get(d.resolution.resolved_by, "Former member"),
            at=d.resolution.at,
            before_release=d.resolution.before_release,
        ),
        difference_unresolved=disagree and d.resolution is None,
    )


@consultations_log_router.get(
    _ONE, action="consultation.read", response_model=ConsultationDetailOut
)
async def consultation_detail_route(consultation_id: UUID, ctx: Ctx) -> ConsultationDetailOut:
    """AUD-28 a/b detail: facts, implementation, links, positions and the resolution."""
    await _on(ctx)
    return await _detail(ctx, consultation_id)


@consultations_log_router.post(
    f"{_ONE}/reopen",
    action="consultation.reopen",
    response_model=ConsultationDetailOut,
    errors=(409,),
)
async def consultation_reopen_route(
    consultation_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConsultationDetailOut:
    """The consultee or the QM owner; 409 `consultation_not_concluded` on an open one."""
    await _human(ctx, "consultation.reopen")
    from abacus.modules.assurance import consultations_log as log

    await log.reopen(ctx, consultation_id)
    return await _detail(ctx, consultation_id)


@consultations_log_router.post(
    f"{_ONE}/links", action="consultation.link", response_model=ConsultationDetailOut
)
async def consultation_link_route(
    consultation_id: UUID, body: ConsultationLinkIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> ConsultationDetailOut:
    """Insert-only; linking the same target twice is a no-op."""
    await _human(ctx, "consultation.link")
    from abacus.modules.assurance import consultations_log as log

    await log.attach(ctx, consultation_id, body.kind, body.target_id)
    return await _detail(ctx, consultation_id)


@consultations_log_router.post(
    f"{_ONE}/positions",
    action="consultation.record_position",
    response_model=ConsultationDetailOut,
)
async def consultation_position_route(
    consultation_id: UUID,
    body: ConsultationPositionIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ConsultationDetailOut:
    """AUD-28 b: the EP's or EQR's own position, in the role they hold on the engagement."""
    await _human(ctx, "consultation.record_position")
    from abacus.modules.assurance import consultations_log as log

    await log.record_position(
        ctx, consultation_id, role=body.role, agrees=body.agrees, position=body.position
    )
    return await _detail(ctx, consultation_id)


@consultations_log_router.post(
    f"{_ONE}/resolve-difference",
    action="consultation.resolve_difference",
    response_model=ConsultationDetailOut,
    errors=(409,),
)
async def consultation_resolve_route(
    consultation_id: UUID,
    body: ConsultationResolutionIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ConsultationDetailOut:
    """The QM owner, fresh MFA (the matrix); one resolution per consultation (409 on a second)."""
    await _human(ctx, "consultation.resolve_difference")
    from abacus.modules.assurance import consultations_log as log

    await log.resolve_difference(ctx, consultation_id, resolution=body.resolution)
    return await _detail(ctx, consultation_id)
