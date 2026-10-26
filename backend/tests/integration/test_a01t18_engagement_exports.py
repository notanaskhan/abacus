"""A-01-T18 against Postgres (TASK-1334; SPEC-344 AC-6 to AC-8; DEC-379, DEC-433): "Undo inside
10 s leaves an undone row and no package, and agent, offshore and stale-MFA requests are
refused."

The services run as the app role (grants, row-level security, the guard trigger); seed rows go
through the superuser. The firm is synthetic so a frozen business clock reaches `abacus_now()`
too (F-04.3), and the database's own window check can be exercised."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import insert, text, update
from sqlalchemy.exc import DBAPIError, IntegrityError

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import Target, uow
from abacus.modules.evidence import export_activities, exports
from abacus.modules.evidence.export_models import EngagementExport
from abacus.modules.identity.api import AuthContext, Forbidden

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(exports, "flag_enabled", on)  # `audits.binder_export` on
    yield
    await dispose_engine()
    settings.cache_clear()
    forget_flags()


@dataclass(frozen=True)
class World:
    seed: Seeder
    tenant: uuid.UUID
    partner: Person
    manager: Person
    staff: Person
    offshore: Person
    walled: Person
    engagement: uuid.UUID
    work_item: uuid.UUID
    binder: uuid.UUID
    foreign_binder: uuid.UUID
    advisory_item: uuid.UUID


async def _binder(
    seed: Seeder, tenant: uuid.UUID, engagement: uuid.UUID, by: uuid.UUID
) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO request_lists (tenant_id, engagement_id, created_at, kind, status, "
            "published_at, published_by) VALUES ($1, $2, clock_timestamp(), 'pbc', 'published', "
            "clock_timestamp(), $3) RETURNING id",
            tenant,
            engagement,
            by,
        ),
    )


@pytest.fixture
async def world(migrated_db: MigratedDatabase) -> World:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    people = [await seed.person(tenant) for _ in range(6)]
    partner, manager, staff, offshore, walled, other = people
    engagements: list[uuid.UUID] = []
    for name in ("Northwind Labs", "Copperleaf"):
        entity = await seed.entity(tenant, name)
        engagement = await seed.engagement(tenant, entity, partner.user_id)
        await seed.member(engagement, partner, "engagement_partner")
        engagements.append(engagement)
    engagement = engagements[0]
    for who, role in ((manager, "manager"), (staff, "staff"), (offshore, "manager")):
        await seed.member(engagement, who, role)  # type: ignore[arg-type]  # the Role literal
    await seed.member(engagement, walled, "manager")
    await seed.run(
        "UPDATE memberships SET offshore = true WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        offshore.user_id,
    )
    client = await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement)
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        walled.user_id,
        client,
        other.user_id,
    )
    work_item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'",
            engagement,
        ),
    )
    advisory = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'advisory_project', 'Advisory', $4) RETURNING id",
            tenant,
            engagement,
            client,
            partner.user_id,
        ),
    )
    binder = await _binder(seed, tenant, engagement, partner.user_id)
    foreign = await _binder(seed, tenant, engagements[1], partner.user_id)
    return World(
        seed,
        tenant,
        partner,
        manager,
        staff,
        offshore,
        walled,
        engagement,
        work_item,
        binder,
        foreign,
        advisory,
    )


async def _create(
    world: World, who: AuthContext, key: str | None = None, **scope: object
) -> exports.ExportView:
    return await exports.create(
        who,
        cast(uuid.UUID, scope.pop("work_item", world.work_item)),
        kind="binder",
        binder_ids=cast(list[uuid.UUID], scope.pop("binder_ids", [])),
        include_unaccepted=False,
        include_audit_trail=True,
        idempotency_key=key or f"key-{uuid.uuid4().hex}",
    )


async def _row(world: World, export_id: uuid.UUID) -> EngagementExport:
    async with tenant_session(TenantContext(world.tenant, "system", "test")) as session:
        row = await session.get(EngagementExport, export_id)
    assert row is not None
    return row


# --- AC-6: create --------------------------------------------------------------------------------


async def test_ac6_create_queues_an_export_behind_a_ten_second_grant(world: World) -> None:
    view = await _create(world, world.partner.context())
    assert (view.status, view.kind, view.format_version) == ("queued", "binder", "1.0")
    assert view.scope.binder_ids == (world.binder,)
    assert view.allowed_actions == ["undo"]
    window = view.not_before - view.requested_at
    assert timedelta(seconds=9) < window <= timedelta(seconds=10, milliseconds=500)
    row = await _row(world, view.id)
    assert (row.requested_by, row.requested_by_kind) == (world.partner.user_id, "human")
    grant = await world.seed.rows(
        "SELECT action, not_before, voided_at, used_at FROM approval_grants WHERE id = $1",
        row.grant_id,
    )
    assert grant[0]["action"] == "export.create"
    assert grant[0]["not_before"] == row.not_before
    assert grant[0]["voided_at"] is None and grant[0]["used_at"] is None
    assert "engagement_export.requested" in await world.seed.actions(world.tenant)
    held = await world.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = $2",
        world.tenant,
        "engagement_export.requested",
    )
    assert held == 1


async def test_ac6_a_retried_key_returns_the_same_export(world: World) -> None:
    first = await _create(world, world.partner.context(), "export-key-0001")
    again = await _create(world, world.partner.context(), "export-key-0001")
    assert again.id == first.id
    assert await world.seed.count("engagement_exports", world.tenant) == 1


async def test_ac6_the_history_and_the_poll_read_it(world: World) -> None:
    made = [await _create(world, world.partner.context()) for _ in range(2)]
    page = await exports.work_item_exports(world.manager.context(), world.work_item, None)
    assert [v.id for v in page.items] == [made[1].id, made[0].id]  # newest first
    assert page.next_cursor is None
    # The manager may read, not undo, the partner's export.
    assert page.items[0].allowed_actions == []
    polled = await exports.read(world.manager.context(), made[0].id)
    assert polled.status == "queued"


# --- AC-7: Undo ----------------------------------------------------------------------------------


async def test_ac7_undo_inside_the_window_leaves_an_undone_row_and_no_package(
    world: World,
) -> None:
    view = await _create(world, world.partner.context())
    undone = await exports.undo(world.partner.context(), view.id)
    assert undone.status == "undone" and undone.allowed_actions == []
    row = await _row(world, view.id)
    assert row.undone_by == world.partner.user_id and row.undone_at is not None
    voided = await world.seed.value(
        "SELECT voided_at FROM approval_grants WHERE id = $1", row.grant_id
    )
    assert voided is not None
    actions = await world.seed.actions(world.tenant)
    assert "engagement_export.undone" in actions and "approval_grant.voided" in actions
    # The build that would follow stops at the grant: nothing is snapshot or packaged.
    with clock.frozen(row.not_before + timedelta(seconds=1)):
        assert await export_activities.start_export(world.tenant, view.id) == "undone"
    assert await world.seed.count("engagement_export_contents", world.tenant) == 0
    assert (await _row(world, view.id)).bundle_sha256 is None


async def test_ac7_undo_after_the_window_or_by_another_person_is_409(world: World) -> None:
    view = await _create(world, world.partner.context())
    with pytest.raises(exports.ExportUndoClosed):
        await exports.undo(world.manager.context(), view.id)  # not the requester
    with (
        clock.frozen(view.not_before + timedelta(seconds=1)),
        pytest.raises(exports.ExportUndoClosed),
    ):
        await exports.undo(world.partner.context(), view.id)
    assert (await _row(world, view.id)).status == "queued"


async def test_ac7_the_database_refuses_an_undo_after_the_window(world: World) -> None:
    """The guard repeats the window on the database's business clock, as the app role."""
    view = await _create(world, world.partner.context())
    row = await _row(world, view.id)
    late = row.not_before + timedelta(seconds=1)
    with clock.frozen(late), pytest.raises(exports.ExportUndoClosed):
        async with uow(world.partner.context().tenant) as tx:
            await exports._undone(tx, row, world.partner.user_id, late)  # pyright: ignore[reportPrivateUsage] -- past the service's own check
    assert (await _row(world, view.id)).status == "queued"


async def test_ac7_the_database_refuses_an_undo_by_anyone_else(world: World) -> None:
    view = await _create(world, world.partner.context())
    with pytest.raises(DBAPIError, match="requester"):
        async with uow(world.manager.context().tenant) as tx:
            await tx.session.execute(
                update(EngagementExport)
                .where(EngagementExport.id == view.id)
                .values(
                    status="undone", undone_at=datetime.now(UTC), undone_by=world.partner.user_id
                )
            )
            tx.record("engagement_export.undone", target=Target(exports.SUBJECT, view.id))


# --- AC-8: what may be exported ------------------------------------------------------------------


async def test_ac8_a_work_item_that_is_not_an_audit_is_422(world: World) -> None:
    with pytest.raises(exports.ExportKindUnsupported):
        await _create(world, world.partner.context(), work_item=world.advisory_item)


async def test_ac8_a_binder_outside_the_work_item_is_422(world: World) -> None:
    with pytest.raises(exports.BinderNotInWorkItem):
        await _create(world, world.partner.context(), binder_ids=[world.foreign_binder])
    with pytest.raises(exports.BinderNotInWorkItem):
        await _create(world, world.partner.context(), binder_ids=[world.binder, uuid.uuid4()])
    assert await world.seed.count("engagement_exports", world.tenant) == 0


# --- refusals ------------------------------------------------------------------------------------


async def test_agent_offshore_stale_mfa_and_staff_requests_are_refused(world: World) -> None:
    partner = world.partner.context()
    agent = replace(partner, tenant=TenantContext(world.tenant, "agent", "agent:x:1"))
    stale = replace(partner, mfa_at=datetime.now(UTC) - timedelta(hours=2))
    for who in (agent, world.offshore.context(), stale, world.staff.context()):
        with pytest.raises(Forbidden):
            await _create(world, who)
    assert await world.seed.count("engagement_exports", world.tenant) == 0


async def test_a_wall_answers_before_the_flag(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def off(_tenant: object, _flag: object) -> bool:
        return False

    monkeypatch.setattr(exports, "flag_enabled", off)
    with pytest.raises(Forbidden) as walled:
        await _create(world, world.walled.context())
    assert walled.value.layer == "wall"  # the API answers 404 (INV-3)
    with pytest.raises(NotFound):  # flag off: 404 for the partner too
        await _create(world, world.partner.context())


async def test_the_database_refuses_a_non_human_requester(world: World) -> None:
    view = await _create(world, world.partner.context())
    row = await _row(world, view.id)
    with pytest.raises(IntegrityError, match="requested_by_kind"):
        async with uow(world.partner.context().tenant) as tx:
            await tx.session.execute(
                insert(EngagementExport).values(
                    id=uuid.uuid4(),
                    tenant_id=world.tenant,
                    engagement_id=world.engagement,
                    work_item_id=world.work_item,
                    client_id=row.client_id,
                    kind="binder",
                    scope=row.scope,
                    format_version="1.0",
                    requested_by=world.partner.user_id,
                    requested_by_kind="agent",
                    mfa_at=row.mfa_at,
                    grant_id=row.grant_id,
                    not_before=row.not_before,
                )
            )


async def test_the_app_role_changes_only_the_status_and_its_stamps(world: World) -> None:
    view = await _create(world, world.partner.context())
    system = TenantContext(world.tenant, "system", "test")
    for statement in (
        text("UPDATE engagement_exports SET kind = 'final_binder' WHERE id = :id"),
        text("DELETE FROM engagement_exports WHERE id = :id"),
    ):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with tenant_session(system) as session:
                await session.execute(statement, {"id": view.id})
    with pytest.raises(DBAPIError, match="permission denied"):  # contents are insert-only
        async with tenant_session(system) as session:
            await session.execute(
                text("DELETE FROM engagement_export_contents WHERE export_id = :id"),
                {"id": view.id},
            )


async def test_another_firm_reads_no_export(world: World, migrated_db: MigratedDatabase) -> None:
    view = await _create(world, world.partner.context())
    other = await Seeder(migrated_db.superuser_dsn).firm()
    async with tenant_session(TenantContext(other, "system", "test")) as session:
        assert await session.get(EngagementExport, view.id) is None
