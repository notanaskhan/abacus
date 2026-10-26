"""G-02-T08 gap (TASK-1363; DEC-458): the unit of work stores each audit event's client and office,
and the explorer relies on them (SPEC-349 AC-4, AC-7; DEC-415 Q9).

- An event's engagement (its scope's, else an engagement target) places it: the engagement's
  client, and the work item's office, else the engagement's, else the client's primary office.
- A client target is its own client. A scope's explicit client must agree with its engagement's.
- Placed rows are part of the hash chain's leaf from insert: the chain verifies over them.
- A walled firm-level reader never sees an event whose stored client is walled, in the list, the
  counts or the detail, even where the ref-based rule alone would show it.
- The Office filter matches the event's stored office.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final, cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.kernel.uow.chain import seal_checkpoint, verify_chain
from abacus.kernel.uow.placement import PlacementMismatch
from abacus.modules.identity.api import AuthContext, current_context

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

LIST: Final = "/v1/audit-events"
Call = Callable[..., Awaitable[httpx.Response]]


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _member(seed: Seeder, tenant: uuid.UUID, name: str, firm_role: str) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
            name,
        ),
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, kind) "
            "VALUES ($1, $2, $3, 'active', 'staff') RETURNING id",
            tenant,
            user,
            firm_role,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=membership,
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    grace: AuthContext  # firm_admin
    ivan: AuthContext  # firm_admin walled from Ashford
    ashford: uuid.UUID
    ashford_client: uuid.UUID
    copperleaf: uuid.UUID
    copperleaf_client: uuid.UUID
    denver: uuid.UUID  # Ashford's engagement office
    boulder: uuid.UUID  # a Copperleaf work item's office
    austin: uuid.UUID  # Copperleaf's primary office (its engagement has none)


async def _office(seed: Seeder, tenant: uuid.UUID, name: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO offices (tenant_id, name) VALUES ($1, $2) RETURNING id", tenant, name
        ),
    )


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'audit_log.explorer', 'true', 'g02t08', 'G-02-T08') "
        "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = EXCLUDED.value",
        tenant,
    )
    grace = await _member(seed, tenant, "Grace Holloway", "firm_admin")
    ivan = await _member(seed, tenant, "Ivan Petrov", "firm_admin")
    ashford = await seed.engagement(
        tenant, await seed.entity(tenant, "Ashford Manufacturing Co."), grace.user_id
    )
    copperleaf = await seed.engagement(
        tenant, await seed.entity(tenant, "Copperleaf Coffee Roasters, Inc."), grace.user_id
    )

    async def client_of(engagement: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement),
        )

    ashford_client, copperleaf_client = await client_of(ashford), await client_of(copperleaf)
    denver = await _office(seed, tenant, "Denver")
    boulder = await _office(seed, tenant, "Boulder")
    austin = await _office(seed, tenant, "Austin")
    await seed.run("UPDATE engagements SET office_id = $1 WHERE id = $2", denver, ashford)
    await seed.run("UPDATE engagements SET office_id = NULL WHERE id = $1", copperleaf)
    await seed.run(
        "UPDATE clients SET primary_office_id = $1 WHERE id = $2", austin, copperleaf_client
    )
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        ivan.user_id,
        ashford_client,
        grace.user_id,
    )
    return World(
        tenant,
        grace,
        ivan,
        ashford,
        ashford_client,
        copperleaf,
        copperleaf_client,
        denver,
        boulder,
        austin,
    )


@pytest.fixture
def as_() -> Callable[[object], Call]:
    def bind(ctx: object) -> Call:
        async def call(method: str, path: str, **kwargs: object) -> httpx.Response:
            app = create_app()
            app.dependency_overrides[current_context] = lambda: ctx
            transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.request(method, path, **kwargs)  # pyright: ignore[reportArgumentType] -- httpx's keyword arguments, passed through

        return call

    return bind


async def _record(
    ctx: TenantContext, action: str, target: Target, scope: Scope | None = None
) -> None:
    async with uow(ctx) as tx:
        tx.record(action, target=target, after=Ref(version=1), scope=scope)


async def _placed(seed: Seeder, world: World, target: object) -> tuple[object, object]:
    rows = await seed.rows(
        "SELECT client_id, office_id FROM audit_events WHERE tenant_id = $1 AND target_id = $2 "
        "ORDER BY seq DESC LIMIT 1",
        world.tenant,
        str(target),
    )
    return rows[0]["client_id"], rows[0]["office_id"]


def _target_ids(response: httpx.Response) -> list[str]:
    assert response.status_code == 200, response.text
    items = cast(list[dict[str, object]], response.json()["items"])
    return [cast(str, cast(dict[str, object], r["target"])["id"]) for r in items]


# --- The unit of work places events -------------------------------------------------------------


async def test_ac7_a_scoped_event_takes_its_engagements_client_and_office(
    world: World, seed: Seeder
) -> None:
    item = uuid.uuid4()
    await _record(
        world.grace.tenant,
        "request_item.received",
        Target("request_item", item),
        Scope(engagement_id=world.ashford),
    )
    assert await _placed(seed, world, item) == (world.ashford_client, world.denver)


async def test_ac7_an_engagement_target_places_itself(world: World, seed: Seeder) -> None:
    await _record(world.grace.tenant, "engagement.renamed", Target("engagement", world.ashford))
    assert await _placed(seed, world, world.ashford) == (world.ashford_client, world.denver)


async def test_ac7_a_work_items_office_wins_then_the_clients_primary_office(
    world: World, seed: Seeder
) -> None:
    work_item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, office_id, "
            "created_by) VALUES ($1, $2, $3, 'tax_return', '2025 Form 1120', $4, $5) "
            "RETURNING id",
            world.tenant,
            world.copperleaf,
            world.copperleaf_client,
            world.boulder,
            world.grace.user_id,
        ),
    )
    with_item, without = uuid.uuid4(), uuid.uuid4()
    await _record(
        world.grace.tenant,
        "request_item.received",
        Target("request_item", with_item),
        Scope(engagement_id=world.copperleaf, work_item_id=work_item),
    )
    await _record(
        world.grace.tenant,
        "request_item.received",
        Target("request_item", without),
        Scope(engagement_id=world.copperleaf),
    )
    assert await _placed(seed, world, with_item) == (world.copperleaf_client, world.boulder)
    # The engagement has no office: the client's primary office (DEC-415 Q9).
    assert await _placed(seed, world, without) == (world.copperleaf_client, world.austin)


async def test_ac7_a_client_target_is_its_own_client(world: World, seed: Seeder) -> None:
    await _record(
        world.grace.tenant, "client_access.granted", Target("client", world.copperleaf_client)
    )
    assert await _placed(seed, world, world.copperleaf_client) == (
        world.copperleaf_client,
        world.austin,
    )


async def test_a_scope_client_that_disagrees_with_its_engagement_is_refused(
    world: World, seed: Seeder
) -> None:
    item = uuid.uuid4()
    with pytest.raises(PlacementMismatch):
        await _record(
            world.grace.tenant,
            "request_item.received",
            Target("request_item", item),
            Scope(engagement_id=world.ashford, client_id=world.copperleaf_client),
        )
    stored = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND target_id = $2",
        world.tenant,
        str(item),
    )
    assert stored == 0  # nothing committed


async def test_an_unscoped_event_keeps_its_explicit_placement_or_none(
    world: World, seed: Seeder
) -> None:
    hold, other = uuid.uuid4(), uuid.uuid4()
    await _record(
        world.grace.tenant,
        "legal_hold.placed",
        Target("legal_hold", hold),
        Scope(client_id=world.ashford_client),
    )
    await _record(world.grace.tenant, "user.updated", Target("user", other))
    assert await _placed(seed, world, hold) == (world.ashford_client, None)
    assert await _placed(seed, world, other) == (None, None)


async def test_placed_events_keep_the_hash_chain_valid(world: World) -> None:
    await _record(
        world.grace.tenant,
        "request_item.received",
        Target("request_item", uuid.uuid4()),
        Scope(engagement_id=world.ashford),
    )
    await _record(
        world.grace.tenant, "client_access.granted", Target("client", world.copperleaf_client)
    )
    assert await seal_checkpoint(world.tenant, settle_seconds=0) is not None
    assert await verify_chain(world.tenant) == []


# --- The explorer relies on them ----------------------------------------------------------------


async def test_ac4_a_walled_reader_never_sees_an_event_whose_stored_client_is_walled(
    world: World, as_: Callable[[object], Call], seed: Seeder
) -> None:
    # Two firm-level holds with firm-safe references: the ref-based rule alone shows both to a
    # walled firm-level reader; the stored client hides the Ashford one.
    walled, open_ = uuid.uuid4(), uuid.uuid4()
    await _record(
        world.grace.tenant,
        "legal_hold.placed",
        Target("legal_hold", walled),
        Scope(client_id=world.ashford_client),
    )
    await _record(
        world.grace.tenant,
        "legal_hold.placed",
        Target("legal_hold", open_),
        Scope(client_id=world.copperleaf_client),
    )
    ivan = await as_(world.ivan)("GET", LIST)
    assert str(walled) not in _target_ids(ivan)
    assert str(open_) in _target_ids(ivan)
    body = ivan.json()
    assert body["total"] == len(body["items"]) == body["counts"]["all"]
    assert str(world.ashford_client) not in ivan.text
    seq = cast(
        int,
        await seed.value(
            "SELECT seq FROM audit_events WHERE tenant_id = $1 AND target_id = $2",
            world.tenant,
            str(walled),
        ),
    )
    assert (await as_(world.ivan)("GET", f"{LIST}/{seq}")).status_code == 404
    grace = await as_(world.grace)("GET", LIST)
    assert {str(walled), str(open_)} <= set(_target_ids(grace))
    shown = (await as_(world.grace)("GET", f"{LIST}/{seq}")).json()
    assert shown["target"]["client_id"] == str(world.ashford_client)


async def test_ac7_the_office_filter_matches_the_events_stored_office(
    world: World, as_: Callable[[object], Call]
) -> None:
    in_denver, in_austin = uuid.uuid4(), uuid.uuid4()
    await _record(
        world.grace.tenant,
        "request_item.received",
        Target("request_item", in_denver),
        Scope(engagement_id=world.ashford),
    )
    await _record(
        world.grace.tenant,
        "request_item.received",
        Target("request_item", in_austin),
        Scope(engagement_id=world.copperleaf),
    )
    denver = await as_(world.grace)("GET", LIST, params={"office_id": str(world.denver)})
    assert _target_ids(denver) == [str(in_denver)]
    assert denver.json()["items"][0]["office_id"] == str(world.denver)
    austin = await as_(world.grace)("GET", LIST, params={"office_id": str(world.austin)})
    assert _target_ids(austin) == [str(in_austin)]
    nowhere = await as_(world.grace)("GET", LIST, params={"office_id": str(world.boulder)})
    assert _target_ids(nowhere) == []
