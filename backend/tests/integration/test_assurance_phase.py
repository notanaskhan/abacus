"""A-01-T05 against Postgres (SPEC-330 AC-9 to AC-14; migration 0134; DEC-262): "Backward, skipped
and agent phase moves are refused and a registered gate provider ends record mode for its phase."

The service runs as the app role (grants and row-level security as production uses them); seed
rows go through the superuser.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from typing import cast

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.flags import forget_flags
from abacus.modules.assurance import api as assurance_api
from abacus.modules.assurance import phase
from abacus.modules.engagements import slots
from abacus.modules.engagements.api import GateFact
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert assurance_api.SUBSCRIPTIONS["gate.met"] is phase.on_gate_met  # G6 to G9 registered


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@dataclass(frozen=True)
class World:
    seed: Seeder
    tenant: uuid.UUID
    partner: AuthContext
    staff: AuthContext
    engagement: uuid.UUID
    work_item: uuid.UUID

    async def phase_row(self) -> asyncpg.Record:
        rows = await self.seed.rows(
            "SELECT phase, phase_source, version, phase_changed_at, ebp_plan_kind, "
            "limited_scope_103a3c FROM assurance_work_items WHERE work_item_id = $1",
            self.work_item,
        )
        return rows[0]

    async def events(self) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT from_phase, to_phase, mode, actor_kind, actor_user_id, gate_ref, "
            "reason_sealed FROM assurance_phase_events WHERE work_item_id = $1 "
            "ORDER BY recorded_at",
            self.work_item,
        )

    async def actions(self) -> list[str]:
        rows = await self.seed.rows(
            "SELECT action FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
            "AND action LIKE 'assurance.%' ORDER BY seq",
            self.tenant,
            str(self.engagement),
        )
        return [str(r["action"]) for r in rows]

    async def outbox(self) -> list[str]:
        rows = await self.seed.rows(
            "SELECT event_type FROM outbox WHERE tenant_id = $1 "
            "AND event_type = 'assurance.phase_changed'",
            self.tenant,
        )
        return [str(r["event_type"]) for r in rows]


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> World:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    partner = await seed.person(tenant)
    staff = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    await seed.member(engagement, partner, "engagement_partner")
    await seed.member(engagement, staff, "staff")
    await seed.confirm(engagement, partner)
    await seed.confirm(engagement, staff)
    work_item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            engagement,
        ),
    )
    return World(seed, tenant, partner.context(), staff.context(), engagement, work_item)


async def test_ac12_a_person_records_the_next_phase_in_one_unit(world: World) -> None:
    move = await phase.record_phase(world.partner, world.work_item, "fieldwork", "Planning done")
    assert (move.from_phase, move.to_phase, move.mode, move.version) == (
        "planning",
        "fieldwork",
        "recorded",
        2,
    )
    row = await world.phase_row()
    assert (row["phase"], row["phase_source"], row["version"]) == ("fieldwork", "recorded", 2)
    assert row["phase_changed_at"] is not None
    [event] = await world.events()
    assert (event["mode"], event["actor_kind"], event["actor_user_id"]) == (
        "recorded",
        "human",
        world.partner.user_id,
    )
    sealed = cast(bytes, event["reason_sealed"])
    assert sealed and b"Planning done" not in sealed  # sealed under the tenant key
    assert await world.actions() == ["assurance.phase_recorded"]
    assert await world.outbox() == ["assurance.phase_changed"]


async def test_ac9_backward_and_repeated_moves_are_refused(world: World) -> None:
    await phase.record_phase(world.partner, world.work_item, "fieldwork")
    with pytest.raises(phase.PhaseBackward):
        await phase.record_phase(world.partner, world.work_item, "planning")
    with pytest.raises(phase.PhaseBackward):
        await phase.record_phase(world.partner, world.work_item, "fieldwork")
    assert len(await world.events()) == 1


async def test_ac9_a_skipped_phase_is_refused(world: World) -> None:
    with pytest.raises(phase.PhaseSkip):
        await phase.record_phase(world.partner, world.work_item, "in_review")
    await phase.record_phase(world.partner, world.work_item, "fieldwork")
    await phase.record_phase(world.partner, world.work_item, "in_review")
    # DV-12: Completion is not offered before DF-05, so it is a skip past Ready to release.
    with pytest.raises(phase.PhaseSkip):
        await phase.record_phase(world.partner, world.work_item, "completion")
    assert (await world.phase_row())["phase"] == "in_review"


async def test_ac10_a_computed_gate_ends_record_mode_for_its_phase(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    # SPEC-314 computes G6 and G7, so Ready to release follows its gates.
    await phase.record_phase(world.partner, world.work_item, "fieldwork")
    await phase.record_phase(world.partner, world.work_item, "in_review")
    with pytest.raises(phase.PhaseFollowsGate):
        await phase.record_phase(world.partner, world.work_item, "ready_to_release")

    async def g4(_tenant: TenantContext, _engagement: uuid.UUID) -> GateFact:
        return GateFact(met=False)

    fresh = await _fresh_item(world)
    monkeypatch.setitem(slots._GATES, "G4", g4)  # pyright: ignore[reportPrivateUsage] -- A-04's provider, registered for the test
    with pytest.raises(phase.PhaseFollowsGate):
        await phase.record_phase(world.partner, fresh, "fieldwork")


async def test_ac11_staff_agents_and_the_system_are_refused(world: World) -> None:
    with pytest.raises(Forbidden):
        await phase.record_phase(world.staff, world.work_item, "fieldwork")
    system = replace(
        world.partner,
        tenant=TenantContext(world.tenant, "system", "test.system"),
    )
    with pytest.raises(Forbidden):
        await phase.record_phase(system, world.work_item, "fieldwork")
    assert await world.events() == []


async def test_ac11_the_table_refuses_a_non_human_recorded_row_and_any_change(
    world: World,
) -> None:
    with pytest.raises(asyncpg.CheckViolationError):
        await world.seed.run(
            "INSERT INTO assurance_phase_events (tenant_id, engagement_id, work_item_id, "
            "from_phase, to_phase, mode, actor_kind, actor_user_id) "
            "VALUES ($1, $2, $3, 'planning', 'fieldwork', 'recorded', 'system', $4)",
            world.tenant,
            world.engagement,
            world.work_item,
            world.partner.user_id,
        )
    await phase.record_phase(world.partner, world.work_item, "fieldwork")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await world.seed.run(
            "UPDATE assurance_phase_events SET to_phase = 'in_review' WHERE work_item_id = $1",
            world.work_item,
        )


async def test_ac13_gate_met_derives_the_phase_once(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def g4(_tenant: TenantContext, _engagement: uuid.UUID) -> GateFact:
        return GateFact(met=True)

    monkeypatch.setitem(slots._GATES, "G4", g4)  # pyright: ignore[reportPrivateUsage] -- A-04's provider, registered for the test
    tenant = TenantContext(world.tenant, "system", "assurance.phase_derive")
    move = await phase.derive_phase(tenant, world.engagement, "G4")
    assert move is not None
    assert (move.to_phase, move.mode) == ("fieldwork", "derived")
    assert await phase.derive_phase(tenant, world.engagement, "G4") is None
    row = await world.phase_row()
    assert (row["phase"], row["phase_source"]) == ("fieldwork", "derived")
    [event] = await world.events()
    assert (event["actor_kind"], event["gate_ref"], event["actor_user_id"]) == (
        "system",
        "G4",
        None,
    )
    assert await world.actions() == ["assurance.phase_derived"]


async def test_ac13_an_unregistered_gate_derives_nothing(world: World) -> None:
    tenant = TenantContext(world.tenant, "system", "assurance.phase_derive")
    assert await phase.derive_phase(tenant, world.engagement, "G4") is None
    assert await phase.derive_phase(tenant, world.engagement, "G1") is None
    assert await world.events() == []


async def test_ac14_the_ebp_profile_takes_its_facts_with_a_version(world: World) -> None:
    made = await phase.update_profile(
        world.partner,
        world.work_item,
        1,
        {"ebp_plan_kind": "dc", "limited_scope_103a3c": True},
    )
    assert (made.ebp_plan_kind, made.limited_scope_103a3c, made.version) == ("dc", True, 2)
    row = await world.phase_row()
    assert (row["ebp_plan_kind"], row["limited_scope_103a3c"]) == ("dc", True)
    with pytest.raises(phase.ProfileStale):
        await phase.update_profile(world.partner, world.work_item, 1, {"ebp_plan_kind": "db"})
    with pytest.raises(Forbidden):
        await phase.update_profile(world.staff, world.work_item, 2, {"ebp_plan_kind": "db"})
    assert await world.actions() == ["assurance.profile_updated"]
    with pytest.raises(asyncpg.CheckViolationError):
        await world.seed.run(
            "UPDATE assurance_work_items SET ebp_plan_kind = 'health_welfare' "
            "WHERE work_item_id = $1",
            world.work_item,
        )


async def _fresh_item(world: World) -> uuid.UUID:
    """A second engagement's assurance work item, still in Planning."""
    entity = await world.seed.entity(world.tenant, name="Second Entity")
    engagement = await world.seed.engagement(world.tenant, entity, world.partner.user_id)
    await world.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'engagement_partner')",
        world.tenant,
        engagement,
        world.partner.user_id,
    )
    await world.seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status, "
        "statement_version, answered_at) VALUES ($1, $2, $3, 'confirmed', 'v1', "
        "clock_timestamp()) ON CONFLICT DO NOTHING",
        world.tenant,
        engagement,
        world.partner.user_id,
    )
    return cast(
        uuid.UUID,
        await world.seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            engagement,
        ),
    )
