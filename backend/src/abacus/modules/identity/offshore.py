"""Offshore members (G-01-T09; DEC-52, ADR P-12; §7216; DEC-319, narrowed by TASK-1207).

Offshore is not a wall: an offshore member sees and works on clients like anyone else with the
same role (F-03 section 4.4). What offshore refuses is the restricted, offshore-conditioned
actions (`not_offshore` in the matrix: `tin.reveal`, `pii.reveal`), at `authorise`'s condition
layer (403). This module adds the ADM-03d read, the assignment guard (a new assignment on a
client needs a valid offshore-disclosure consent, T-01's provider through
`register_consent_check('offshore_disclosure', ...)`; unregistered, none is valid: fail closed)
and the TIN masking hook. The two policy toggles ("Block offshore assignment without consent",
"Mask TINs for restricted members") are code, always on: there is nothing to switch off.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import cast, get_args
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text

from abacus.kernel.classification import flags_of, mask
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.modules.identity.authz import Resource, authorise
from abacus.modules.identity.context import Actor, AgentContext, AuthContext
from abacus.modules.identity.repository import member_facts, walled_clients
from abacus.modules.identity.slots import OFFSHORE_DISCLOSURE, consent_given, consented_count


class OffshoreConsentRequired(DomainConflict):
    """An offshore member can't be assigned to a client without a valid offshore-disclosure
    consent (AC9.3)."""

    code = "offshore_consent_required"


@dataclass(frozen=True)
class OffshoreGroup:
    member_ids: list[UUID]
    consented_client_count: int


async def offshore_group(ctx: AuthContext) -> OffshoreGroup:
    """ADM-03d: who is offshore, and how many clients a consent covers (0 until T-01)."""
    await authorise(ctx, "firm.read_settings", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            text(
                "SELECT user_id FROM memberships WHERE kind = 'staff' AND status = 'active' "
                "AND offshore ORDER BY created_at, user_id"
            )
        )
        members = list(rows.scalars())
    return OffshoreGroup(members, await consented_count(ctx.tenant, OFFSHORE_DISCLOSURE))


async def is_offshore(tenant: TenantContext, user_id: UUID) -> bool:
    member = await member_facts(tenant, user_id)
    return member is not None and not member.client and member.offshore


async def assert_assignable(tenant: TenantContext, user_id: UUID, client_id: UUID) -> None:
    """Before anyone is given work on a client (a work-item assignment, an engagement team):
    walled from it answers 404 like an unknown person; offshore without a valid consent is 409
    `offshore_consent_required` (AC9.3, fail closed)."""
    if client_id in await walled_clients(tenant, user_id):
        raise NotFound("person")
    if await is_offshore(tenant, user_id) and not await consent_given(
        tenant, client_id, OFFSHORE_DISCLOSURE, system_now()
    ):
        raise OffshoreConsentRequired(facts={"user_id": str(user_id)})


def _person(ctx: Actor) -> UUID:
    if isinstance(ctx, AuthContext):
        return ctx.user_id
    if isinstance(ctx, AgentContext):
        return ctx.initiator.user_id
    return ctx.on_behalf_of


def _optional(annotation: object) -> bool:
    return type(None) in get_args(annotation)


def _masked[M: BaseModel](model: M) -> M:
    changes: dict[str, object] = {}
    for name, field in type(model).model_fields.items():
        value = getattr(model, name)
        flags = flags_of(field)
        if flags.pii_kind == "tin" and value is not None:
            # Null where the field allows it (its shape may not fit a mask), else the mask.
            changes[name] = None if _optional(field.annotation) else mask(str(value), "tin")
        elif isinstance(value, BaseModel):
            changes[name] = _masked(value)
        elif isinstance(value, list):
            items = cast(list[object], value)
            changes[name] = [_masked(v) if isinstance(v, BaseModel) else v for v in items]
    return model.model_copy(update=changes) if changes else model


async def mask_tins_for[M: BaseModel](ctx: Actor, model: M) -> M:
    """AC9.4: a response for an offshore principal (or what acts for one) carries every field
    tagged `pii_kind=tin` masked or null, nested models included; anyone else gets it as is."""
    if isinstance(ctx, AuthContext) and ctx.is_support:
        return model
    if not await is_offshore(ctx.tenant, _person(ctx)):
        return model
    return _masked(model)


async def hidden_clients(
    tenant: TenantContext, user_id: UUID, client_ids: Iterable[UUID]
) -> frozenset[UUID]:
    """Of these clients, the ones that must read as unknown to the person: walled off from them
    (ADR-026). For code that filters or refuses by client outside `authorise` and `visible()`
    (pickers, duplicate checks, recipient lists, the wall register). Offshore hides nothing
    (TASK-1207, DEC-319): it refuses only the `not_offshore` actions, in `authorise`."""
    wanted = list(dict.fromkeys(client_ids))
    if not wanted:
        return frozenset()
    walled = await walled_clients(tenant, user_id)
    return frozenset(c for c in wanted if c in walled)
