"""ENG-02's status menu against Postgres (TASK-1198, carried from P-07-T28; DEC-328): "Active ⇄
On hold…" with a reason code, through F-03-T13's transition table. A person with fresh MFA holds
and resumes; each move writes one audit event and one `engagement.status_changed` in the same
unit of work; any other state answers 409 `illegal_transition`; an agent is refused before
anything is written; the routes answer for every firm (`engagements.v2` retired with P-07-T59)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel.db import TenantContext, configure_engine
from abacus.kernel.db.session import ActorKind
from abacus.kernel.flags import forget_flags
from abacus.modules.engagements import contract
from abacus.modules.engagements.transitions import (
    HOLD_REASON_CODES,
    HOLD_REASONS,
    IllegalTransition,
)
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


class _World:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed

    async def make(self) -> _World:
        forget_flags()
        self.tenant = await self.seed.firm()
        self.partner: Person = await self.seed.person(self.tenant)
        self.staff: Person = await self.seed.person(self.tenant)
        entity = await self.seed.entity(self.tenant)
        self.engagement = await self.seed.engagement(self.tenant, entity, self.partner.user_id)
        await self.seed.member(self.engagement, self.partner, "engagement_partner")
        await self.seed.member(self.engagement, self.staff, "staff")
        await self.status("active")
        return self

    async def status(self, to: str | None = None) -> str:
        if to is not None:
            await self.seed.run(
                "UPDATE engagements SET status = $2 WHERE id = $1", self.engagement, to
            )
        return str(
            await self.seed.value("SELECT status FROM engagements WHERE id = $1", self.engagement)
        )

    def ctx(self, who: Person, *, kind: ActorKind = "human", mfa_minutes: int = 1) -> AuthContext:
        tenant = TenantContext(self.tenant, kind, str(who.user_id))
        at = datetime.now(UTC) - timedelta(minutes=mfa_minutes)
        return AuthContext(tenant, who.user_id, uuid.uuid4(), None, at)

    async def count(self, sql: str) -> int:
        return int(str(await self.seed.value(sql, self.tenant)))


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> _World:
    configure_engine(migrated_db.app_url)
    return await _World(Seeder(migrated_db.superuser_dsn)).make()


async def test_the_api_reasons_are_the_transition_tables() -> None:
    assert set(contract.HoldReason.__args__) == HOLD_REASONS


async def test_hold_with_a_reason_then_resume(world: _World) -> None:
    held = await contract.hold_engagement_route(
        world.engagement,
        contract.EngagementHoldIn(reason="fees_outstanding"),
        world.ctx(world.partner),
    )
    assert (held.status, held.hold_reason) == ("on_hold", "fees_outstanding")
    assert await world.status() == "on_hold"
    resumed = await contract.resume_engagement_route(world.engagement, world.ctx(world.partner))
    assert resumed.status == "active" and resumed.hold_reason is None
    assert await world.status() == "active"
    audited = await world.count(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
        "AND action IN ('engagement.held', 'engagement.resumed') AND actor_kind = 'human'"
    )
    assert audited == 2
    rows = await world.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'engagement.status_changed' ORDER BY occurred_at",
        world.tenant,
    )
    assert len(rows) == 2


async def test_the_record_names_the_hold_reason_only_while_on_hold(world: _World) -> None:
    """DEC-344: ENG-02's status pill reads the reason from the record (`hold_reason`)."""
    who = world.ctx(world.partner)
    assert (await contract.engagement_record_route(world.engagement, who)).hold_reason is None
    await contract.hold_engagement_route(
        world.engagement, contract.EngagementHoldIn(reason="client_unresponsive"), who
    )
    record = await contract.engagement_record_route(world.engagement, who)
    assert (record.status, record.hold_reason) == ("on_hold", "client_unresponsive")
    assert "engagement.hold" in record.allowed_actions
    await contract.resume_engagement_route(world.engagement, who)
    record = await contract.engagement_record_route(world.engagement, who)
    assert (record.status, record.hold_reason) == ("active", None)


async def test_only_an_active_engagement_is_held_and_archived_is_refused(world: _World) -> None:
    await world.status("archived")
    with pytest.raises(Forbidden) as archived:  # authorised first: archived writes are refused
        await contract.hold_engagement_route(
            world.engagement, contract.EngagementHoldIn(reason="other"), world.ctx(world.partner)
        )
    assert archived.value.layer == "attribute"  # `archived_write: deny`
    await world.status("active")
    with pytest.raises(IllegalTransition):  # resume only from on hold
        await contract.resume_engagement_route(world.engagement, world.ctx(world.partner))
    assert await world.status() == "active"


async def test_staff_stale_mfa_and_an_agent_are_refused_and_nothing_is_written(
    world: _World,
) -> None:
    body = contract.EngagementHoldIn(reason="scope_change")
    with pytest.raises(Forbidden):
        await contract.hold_engagement_route(world.engagement, body, world.ctx(world.staff))
    with pytest.raises(Forbidden):  # `mfa_recent`
        await contract.hold_engagement_route(
            world.engagement, body, world.ctx(world.partner, mfa_minutes=24 * 60)
        )
    with pytest.raises(Forbidden):  # INV-1: never an agent principal
        await contract.hold_engagement_route(
            world.engagement, body, world.ctx(world.partner, kind="agent")
        )
    assert await world.status() == "active"
    assert (
        await world.count(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'engagement.held'"
        )
        == 0
    )


async def test_the_routes_answer_without_a_flag(migrated_db: MigratedDatabase) -> None:
    """`engagements.v2` retired with P-07-T59 (DEC-905): no flag row, and the hold goes through."""
    configure_engine(migrated_db.app_url)
    plain = await _World(Seeder(migrated_db.superuser_dsn)).make()
    await contract.hold_engagement_route(
        plain.engagement, contract.EngagementHoldIn(reason="other"), plain.ctx(plain.partner)
    )
    assert await plain.status() == "on_hold"


# --- Security review (DEC-328) --------------------------------------------------------------


async def test_review_the_reason_is_kept_on_the_engagement_and_in_the_audit_row(
    world: _World,
) -> None:
    await contract.hold_engagement_route(
        world.engagement,
        contract.EngagementHoldIn(reason="scope_change"),
        world.ctx(world.partner),
    )
    kept = await world.seed.value(
        "SELECT hold_reason FROM engagements WHERE id = $1", world.engagement
    )
    assert kept == "scope_change"
    after = await world.seed.value(
        "SELECT after_ref->>'reason_code' FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'engagement.held'",
        world.tenant,
    )
    assert HOLD_REASON_CODES[int(str(after))] == "scope_change"
    await contract.resume_engagement_route(world.engagement, world.ctx(world.partner))
    cleared = await world.seed.value(
        "SELECT hold_reason FROM engagements WHERE id = $1", world.engagement
    )
    assert cleared is None


async def test_review_a_walled_member_gets_404_whatever_the_status(world: _World) -> None:
    client = await world.seed.value(
        "SELECT client_id FROM engagements WHERE id = $1", world.engagement
    )
    await world.seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        world.tenant,
        world.partner.user_id,
        client,
        world.staff.user_id,
    )
    for status in ("active", "delivered", "prospect"):
        await world.status(status)
        # The wall layer, which the API answers 404 (`api.app`): never 409 naming the state.
        with pytest.raises(Forbidden) as walled:
            await contract.hold_engagement_route(
                world.engagement,
                contract.EngagementHoldIn(reason="other"),
                world.ctx(world.partner),
            )
        assert walled.value.layer == "wall"


async def test_review_only_the_partner_lifts_an_independence_review_hold(world: _World) -> None:
    manager: Person = await world.seed.person(world.tenant)
    await world.seed.member(world.engagement, manager, "manager")
    await contract.hold_engagement_route(
        world.engagement,
        contract.EngagementHoldIn(reason="independence_review"),
        world.ctx(manager),
    )
    with pytest.raises(Forbidden):
        await contract.resume_engagement_route(world.engagement, world.ctx(manager))
    assert await world.status() == "on_hold"
    await contract.resume_engagement_route(world.engagement, world.ctx(world.partner))
    assert await world.status() == "active"
    # Any other reason, the manager lifts it.
    await contract.hold_engagement_route(
        world.engagement, contract.EngagementHoldIn(reason="fees_outstanding"), world.ctx(manager)
    )
    await contract.resume_engagement_route(world.engagement, world.ctx(manager))
    assert await world.status() == "active"
