"""A-06-T11: the minimal consultation record (A-06 §4.2; DEC-83; DEC-2421).

A person with `consultation.create` raises a question to a named firm member on the work item; only
that member concludes it (the service answers 403, and 0644's guard refuses anyone else). The
question and conclusion are sealed. Everyone with `consultation.create` reads the work item's
consultations; someone consulted reads the ones naming them. The firm log and AUD-28 are Q-05's.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, allowed_actions, is_active_member, names_of

TARGET: Final = "consultation"
_FINGERPRINT: Final = "assurance.consultation"
_OF_WORK_ITEM: Final = (
    "SELECT id, work_item_id, ref, question_sealed, raised_by, consulted_with_user_id, status, "
    "conclusion_sealed, concluded_at, created_at FROM consultations WHERE work_item_id = :w "
    "AND (CAST(:all AS boolean) OR consulted_with_user_id = :me) ORDER BY created_at, ref"
)
_ONE: Final = (
    "SELECT id, work_item_id, ref, question_sealed, raised_by, consulted_with_user_id, status, "
    "conclusion_sealed, concluded_at, created_at FROM consultations WHERE id = :id"
)


class NotTheConsultedPerson(DomainForbidden):
    code = "not_the_consulted_person"


class ConsultationConcluded(DomainConflict):
    code = "consultation_concluded"


@dataclass(frozen=True)
class Consultation:
    id: UUID
    work_item_id: UUID
    ref: str
    question: str
    raised_by_name: str
    consulted_with_user_id: UUID
    consulted_with_name: str
    status: str
    conclusion: str | None
    concluded_at: datetime | None
    created_at: datetime
    allowed_actions: tuple[str, ...]


async def _text(ctx: AuthContext, sealed: object) -> str:
    return (await open_sealed(ctx.tenant_id, cast(bytes, sealed), _FINGERPRINT)).decode()


async def _shaped(ctx: AuthContext, rows: list[RowMapping]) -> list[Consultation]:
    people = {cast(UUID, r[k]) for r in rows for k in ("raised_by", "consulted_with_user_id")}
    names = await names_of(sorted(people, key=str)) if people else {}
    shaped: list[Consultation] = []
    for r in rows:
        consulted = cast(UUID, r["consulted_with_user_id"])
        concluded = r["conclusion_sealed"]
        shaped.append(
            Consultation(
                id=cast(UUID, r["id"]),
                work_item_id=cast(UUID, r["work_item_id"]),
                ref=str(r["ref"]),
                question=await _text(ctx, r["question_sealed"]),
                raised_by_name=names.get(cast(UUID, r["raised_by"]), ""),
                consulted_with_user_id=consulted,
                consulted_with_name=names.get(consulted, ""),
                status=str(r["status"]),
                conclusion=None if concluded is None else await _text(ctx, concluded),
                concluded_at=cast(datetime | None, r["concluded_at"]),
                created_at=cast(datetime, r["created_at"]),
                allowed_actions=(
                    ("consultation.conclude",)
                    if r["status"] == "open" and consulted == ctx.user_id
                    else ()
                ),
            )
        )
    return shaped


async def consultations_of(ctx: AuthContext, work_item_id: UUID) -> list[Consultation]:
    """The work item's consultations, oldest first (the route authorised `consultation.read`)."""
    engagement_id = cast(UUID, await work_item_engagement(ctx.tenant, work_item_id))
    ref = await get_ref(ctx, engagement_id)
    everyone = bool(await allowed_actions(ctx, ref.resource(), ("consultation.create",)))
    async with tenant_session(ctx.tenant) as session:
        rows = (
            (
                await session.execute(
                    text(_OF_WORK_ITEM),
                    {"w": work_item_id, "all": everyone, "me": ctx.user_id},
                )
            )
            .mappings()
            .all()
        )
    return await _shaped(ctx, list(rows))


async def raise_consultation(
    ctx: AuthContext, work_item_id: UUID, *, question: str, consulted_with_user_id: UUID
) -> Consultation:
    """`POST …/consultations` (the route authorised `consultation.create`). The person consulted
    is another active member of the firm."""
    if consulted_with_user_id == ctx.user_id or not await is_active_member(
        ctx.tenant_id, consulted_with_user_id
    ):
        raise DomainInvalid(facts={"field": "consulted_with_user_id"})
    engagement_id = cast(UUID, await work_item_engagement(ctx.tenant, work_item_id))
    sealed = await seal(ctx.tenant_id, question.strip().encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        await lock_ref(tx, engagement_id)
        number = (
            await tx.session.execute(
                text("SELECT count(*) + 1 FROM consultations WHERE work_item_id = :w"),
                {"w": work_item_id},
            )
        ).scalar_one()
        consultation_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO consultations (tenant_id, engagement_id, work_item_id, ref, "
                    "question_sealed, raised_by, consulted_with_user_id) VALUES (:t, :e, :w, "
                    ":ref, :q, :by, :with) RETURNING id"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "ref": f"C-{number:02d}",
                    "q": sealed,
                    "by": ctx.user_id,
                    "with": consulted_with_user_id,
                },
            )
        ).scalar_one()
        tx.record(
            "consultation.raised",
            target=Target(TARGET, consultation_id),
            after=Ref(consulted=consulted_with_user_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return await consultation(ctx, consultation_id)


async def consultation(ctx: AuthContext, consultation_id: UUID) -> Consultation:
    async with tenant_session(ctx.tenant) as session:
        row = (
            (
                await session.execute(
                    text(_ONE),
                    {"id": consultation_id},
                )
            )
            .mappings()
            .first()
        )
    if row is None:
        raise NotFound(TARGET)
    return (await _shaped(ctx, [row]))[0]


async def work_item_of(tenant: TenantContext, consultation_id: UUID) -> UUID:
    """The work item the conclude route gates on; every consultation raised here has one."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT work_item_id FROM consultations WHERE id = :id"),
            {"id": consultation_id},
        )
    if not isinstance(found, UUID):
        raise NotFound(TARGET)
    return found


async def conclude(ctx: AuthContext, consultation_id: UUID, *, conclusion: str) -> Consultation:
    """`POST /v1/consultations/{id}/conclude`: the person consulted, once."""
    found = await consultation(ctx, consultation_id)
    if found.consulted_with_user_id != ctx.user_id:
        raise NotTheConsultedPerson
    engagement_id = cast(UUID, await work_item_engagement(ctx.tenant, found.work_item_id))
    sealed = await seal(ctx.tenant_id, conclusion.strip().encode(), _FINGERPRINT)
    async with uow(ctx.tenant) as tx:
        moved = (
            await tx.session.execute(
                text(
                    "UPDATE consultations SET status = 'concluded', conclusion_sealed = :c, "
                    "concluded_at = clock_timestamp() WHERE id = :id AND status = 'open' "
                    "RETURNING id"
                ),
                {"c": sealed, "id": consultation_id},
            )
        ).first()
        if moved is None:
            raise ConsultationConcluded
        tx.record(
            "consultation.concluded",
            target=Target(TARGET, consultation_id),
            after=Ref(consulted=ctx.user_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=found.work_item_id),
        )
    return await consultation(ctx, consultation_id)
