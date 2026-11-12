"""T-05-T22 (TASK-7405; T-05 §4.2 M3; DEC-52, DEC-232, DEC-4404): partner TINs and an entity
return's TRI, against Postgres.

Row acceptance: "A partner's TIN is sealed and revealed only by an onshore person with recent MFA,
never stored in an audit row; the entity return's data subjects resolve to the partnership; its
workbook and memo are retention record types under legal holds."
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import asyncpg
import pytest

from abacus.ai_gateway import DataSubject
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.organisations.api import TinInvalid
from abacus.modules.tax import entity_tri, partner_tins

from .support import Person, Seeder, World

pytestmark = pytest.mark.asyncio
TIN = "12-3456789"


def _ctx(who: Person, *, mfa_age: timedelta | None = timedelta(0)) -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        None,
        None if mfa_age is None else datetime.now(UTC) - mfa_age,
    )


async def _entity_return(seed: Seeder, world: World) -> uuid.UUID:
    client = await seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.engagement_id
    )
    item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by, period_end) VALUES ($1, $2, $3, $4, 'tax_return', "
            "'Harborview 1065', $5, '2025-12-31') RETURNING id",
            world.tenant_id,
            world.engagement_id,
            client,
            world.entity_id,
            world.requester.user_id,
        ),
    )
    await seed.run(
        "INSERT INTO tax_returns (tenant_id, work_item_id, engagement_id, client_entity_id, "
        "form, tax_year) VALUES ($1, $2, $3, $4, '1065', 2025)",
        world.tenant_id,
        item,
        world.engagement_id,
        world.entity_id,
    )
    return item


async def _partner(seed: Seeder, world: World, item: uuid.UUID) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO partners (tenant_id, engagement_id, work_item_id, kind, display_name, "
            "entity_kind, ord) VALUES ($1, $2, $3, 'lp', 'Okafor Family Trust', 'trust', 1) "
            "RETURNING id",
            world.tenant_id,
            world.engagement_id,
            item,
        ),
    )


async def _manager(seed: Seeder, world: World) -> Person:
    who = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, who, "manager")
    return who


async def _sealed(seed: Seeder, world: World) -> tuple[uuid.UUID, uuid.UUID, Person]:
    item = await _entity_return(seed, world)
    partner = await _partner(seed, world, item)
    hannah = await _manager(seed, world)
    ctx = _ctx(hannah)
    async with uow(ctx.tenant) as tx:
        masked = await partner_tins.seal_partner_tin(tx, ctx, partner, TIN, "ein")
    assert (masked.kind, masked.last4) == ("ein", "6789")
    return item, partner, hannah


async def test_a_partner_tin_is_sealed_with_its_last_four_and_never_in_an_audit_row(
    seed: Seeder, world: World
) -> None:
    _, partner, _ = await _sealed(seed, world)
    row = await seed.rows(
        "SELECT tin_sealed, tin_last4, tin_kind FROM partners WHERE id = $1", partner
    )
    sealed = cast(bytes, row[0]["tin_sealed"])
    assert row[0]["tin_last4"] == "6789" and row[0]["tin_kind"] == "ein"
    assert b"123456789" not in sealed and b"6789" not in sealed
    leaked = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND (after_ref::text LIKE "
        "'%123456789%' OR before_ref::text LIKE '%123456789%')",
        world.tenant_id,
    )
    assert leaked == 0


async def test_an_invalid_tin_or_kind_is_refused_without_echoing_it(
    seed: Seeder, world: World
) -> None:
    item = await _entity_return(seed, world)
    partner = await _partner(seed, world, item)
    ctx = _ctx(await _manager(seed, world))
    async with uow(ctx.tenant) as tx:
        with pytest.raises(TinInvalid) as refused:
            await partner_tins.seal_partner_tin(tx, ctx, partner, "000-00-0000", "ssn")
    assert "000" not in str(refused.value.facts or {})


async def test_the_reveal_is_one_row_and_one_event_naming_the_reason_never_the_value(
    seed: Seeder, world: World
) -> None:
    _, partner, hannah = await _sealed(seed, world)
    revealed = await partner_tins.reveal_partner_tin(_ctx(hannah), partner, "prepare_return")
    assert revealed.value == "123456789" and revealed.kind == "ein"
    rows = await seed.rows(
        "SELECT user_id, reason_code, actor_kind FROM partner_tin_reveals WHERE partner_id = $1",
        partner,
    )
    assert [(r["user_id"], r["reason_code"], r["actor_kind"]) for r in rows] == [
        (hannah.user_id, "prepare_return", "human")
    ]
    events = await seed.rows(
        "SELECT after_ref::text AS after FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'partner_tin.revealed'",
        world.tenant_id,
    )
    assert len(events) == 1 and "123456789" not in str(events[0]["after"])


async def test_a_stale_second_factor_steps_up_and_reveals_nothing(
    seed: Seeder, world: World
) -> None:
    _, partner, hannah = await _sealed(seed, world)
    for age in (None, timedelta(hours=2)):
        with pytest.raises(partner_tins.PartnerTinRevealNeedsMfa):
            await partner_tins.reveal_partner_tin(
                _ctx(hannah, mfa_age=age), partner, "review_return"
            )
    assert (
        await seed.value("SELECT count(*) FROM partner_tin_reveals WHERE partner_id = $1", partner)
        == 0
    )


async def test_an_offshore_person_or_a_senior_cannot_reveal(seed: Seeder, world: World) -> None:
    _, partner, _ = await _sealed(seed, world)
    senior = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, senior, "senior")
    with pytest.raises(Forbidden):
        await partner_tins.reveal_partner_tin(_ctx(senior), partner, "prepare_return")
    offshore = await _manager(seed, world)
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        world.tenant_id,
        offshore.user_id,
    )
    with pytest.raises(Forbidden):
        await partner_tins.reveal_partner_tin(_ctx(offshore), partner, "prepare_return")


async def test_the_database_refuses_an_agents_reveal_row_and_any_change(
    seed: Seeder, world: World
) -> None:
    item, partner, hannah = await _sealed(seed, world)
    insert = (
        "INSERT INTO partner_tin_reveals (tenant_id, engagement_id, work_item_id, partner_id, "
        "user_id, reason_code, mfa_at) VALUES ($1, $2, $3, $4, $5, 'prepare_return', now())"
    )
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.as_actor(
            world.tenant_id,
            ("agent", str(hannah.user_id)),
            insert,
            world.tenant_id,
            world.engagement_id,
            item,
            partner,
            hannah.user_id,
        )
    await partner_tins.reveal_partner_tin(_ctx(hannah), partner, "verify_identity")
    with pytest.raises(asyncpg.PostgresError):
        await seed.run("UPDATE partner_tin_reveals SET reason_code = 'review_return'")
    with pytest.raises(asyncpg.PostgresError):
        await seed.run("DELETE FROM partner_tin_reveals")


async def test_the_entity_returns_subject_is_the_partnership_for_its_year(
    seed: Seeder, world: World
) -> None:
    item = await _entity_return(seed, world)
    tenant = TenantContext(world.tenant_id, "system", "test")
    assert await entity_tri.entity_return_subjects(tenant, item) == (
        DataSubject(world.entity_id, 2025),
    )
    unknown = await entity_tri.entity_return_subjects(tenant, uuid.uuid4())
    assert unknown == (DataSubject(None, None),)  # fails closed at the gateway


async def test_the_workbook_and_memo_are_kept_while_on_hold_or_without_a_policy(
    seed: Seeder, world: World
) -> None:
    item = await _entity_return(seed, world)
    tenant = TenantContext(world.tenant_id, "system", "test")
    filed = datetime(2026, 3, 15, tzinfo=UTC)
    later = datetime(2040, 1, 1, tzinfo=UTC)
    for record in ("tax_workbook", "preparer_memo"):
        # No policy and no floor loaded: never releasable (fail closed).
        assert await entity_tri.releasable(tenant, item, record, filed, later) is False
    assert await entity_tri.on_hold(tenant, item) is False
    client: Any = await seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.engagement_id
    )
    await seed.run(
        "INSERT INTO legal_holds (tenant_id, scope_kind, client_id, engagement_id, status, "
        "reason_code, placed_by) VALUES ($1, 'engagement', $2, $3, 'active', 'litigation', $4)",
        world.tenant_id,
        client,
        world.engagement_id,
        world.requester.user_id,
    )
    assert await entity_tri.on_hold(tenant, item) is True
    with pytest.raises(ValueError, match="not an entity return record type"):
        await entity_tri.retain_until(tenant, "client_document", filed)
