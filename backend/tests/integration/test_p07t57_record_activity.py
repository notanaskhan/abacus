"""P-07-T57 (TASK-1623; DEC-718): CLI-02's and ENG-02's Activity lines over the audit trail.

"Activity lists the Thornbury intake, acceptance and team events with person attribution and
nothing from walled clients" (P-07-T57 acceptance):

- The client's own events (no engagement) and its engagement's events, newest first, each in the
  actor grammar with the person named.
- A manager staffed on Thornbury reads both lists; nothing from another client appears.
- A reader walled from Ashford gets 404 for Ashford's records, and a Thornbury event whose
  references name Ashford is hidden from them (and shown to an unwalled reader).
- A client principal gets 404.
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
from abacus.modules.identity.api import AuthContext, current_context

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

Call = Callable[..., Awaitable[httpx.Response]]
FLAGS: Final = ("clients.v2", "engagements.v2")


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


async def _member(
    seed: Seeder, tenant: uuid.UUID, name: str, firm_role: str | None
) -> AuthContext:
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
    grace: AuthContext  # firm_admin
    ivan: AuthContext  # firm_admin walled from Ashford
    priya: AuthContext  # manager on Thornbury only
    thornbury: uuid.UUID
    thornbury_client: uuid.UUID
    ashford: uuid.UUID
    ashford_client: uuid.UUID


@pytest.fixture
async def world(seed: Seeder) -> World:
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'p07t57', 'P-07-T57') "
            "ON CONFLICT (tenant_id, flag) DO UPDATE SET value = EXCLUDED.value",
            tenant,
            flag,
        )
    grace = await _member(seed, tenant, "Grace Holloway", "firm_admin")
    ivan = await _member(seed, tenant, "Ivan Petrov", "firm_admin")
    priya = await _member(seed, tenant, "Priya Raman", None)
    thornbury = await seed.engagement(
        tenant, await seed.entity(tenant, "Walter Thornbury"), grace.user_id
    )
    ashford = await seed.engagement(
        tenant, await seed.entity(tenant, "Ashford Manufacturing Co."), grace.user_id
    )
    await seed.member(thornbury, Person(priya.user_id, tenant), "manager")

    async def client_of(engagement: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement),
        )

    thornbury_client, ashford_client = await client_of(thornbury), await client_of(ashford)
    await seed.run(
        "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
        "VALUES ($1, $2, $3, $4)",
        tenant,
        ivan.user_id,
        ashford_client,
        grace.user_id,
    )
    return World(grace, ivan, priya, thornbury, thornbury_client, ashford, ashford_client)


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
    ctx: AuthContext,
    action: str,
    target: Target,
    scope: Scope | None = None,
    after: Ref | None = None,
) -> None:
    async with uow(ctx.tenant) as tx:
        tx.record(action, target=target, after=after or Ref(version=1), scope=scope)


async def _history(world: World) -> None:
    g = world.grace
    await _record(g, "client_intake.submitted", Target("client", world.thornbury_client))
    await _record(
        g,
        "acceptance.decided",
        Target("engagement", world.thornbury),
        Scope(engagement_id=world.thornbury),
    )
    await _record(g, "team.approved", Target("engagement", world.thornbury))
    await _record(
        g,
        "acceptance.decided",
        Target("engagement", world.ashford),
        Scope(engagement_id=world.ashford),
    )


def _items(response: httpx.Response) -> list[dict[str, object]]:
    assert response.status_code == 200, response.text
    return cast(list[dict[str, object]], response.json()["items"])


def _actions(response: httpx.Response) -> list[str]:
    return [cast(str, r["action"]) for r in _items(response)]


async def test_ac_thornbury_activity_lists_intake_acceptance_and_team_with_people(
    world: World, as_: Callable[[object], Call]
) -> None:
    await _history(world)
    client = await as_(world.grace)("GET", f"/v1/clients/{world.thornbury_client}/activity")
    assert _actions(client) == ["team.approved", "acceptance.decided", "client_intake.submitted"]
    for row in _items(client):
        actor = cast(dict[str, object], row["actor"])
        assert actor["kind"] == "person"
        assert cast(dict[str, object], actor["person"])["display_name"] == "Grace Holloway"
        assert row["ip"] is None
    engagement = await as_(world.grace)(
        "GET", f"/v1/engagements/{world.thornbury}/record-activity"
    )
    assert _actions(engagement) == ["team.approved", "acceptance.decided"]


async def test_ac_the_staffed_manager_reads_thornbury_and_nothing_of_ashford(
    world: World, as_: Callable[[object], Call]
) -> None:
    await _history(world)
    call = as_(world.priya)
    assert _actions(await call("GET", f"/v1/engagements/{world.thornbury}/record-activity")) == [
        "team.approved",
        "acceptance.decided",
    ]
    # Her engagement role holds the read at the client, so the client's own events show too;
    # Ashford's never do (DEC-718).
    client = await call("GET", f"/v1/clients/{world.thornbury_client}/activity")
    assert _actions(client) == ["team.approved", "acceptance.decided", "client_intake.submitted"]
    refused = await call("GET", f"/v1/engagements/{world.ashford}/record-activity")
    assert refused.status_code in (403, 404)


async def test_ac_nothing_from_walled_clients(world: World, as_: Callable[[object], Call]) -> None:
    await _history(world)
    await _record(
        world.grace,
        "entity_relationship.created",
        Target("client", world.thornbury_client),
        after=Ref(other_client_id=world.ashford_client),
    )
    ivan = as_(world.ivan)
    walled_client = await ivan("GET", f"/v1/clients/{world.ashford_client}/activity")
    unknown = await ivan("GET", f"/v1/clients/{uuid.uuid4()}/activity")
    assert walled_client.status_code == unknown.status_code == 200  # as if it never existed
    assert _items(walled_client) == _items(unknown) == []
    walled_engagement = await ivan("GET", f"/v1/engagements/{world.ashford}/record-activity")
    assert walled_engagement.status_code == 404
    seen = _actions(await ivan("GET", f"/v1/clients/{world.thornbury_client}/activity"))
    assert "entity_relationship.created" not in seen
    assert "client_intake.submitted" in seen
    grace = _actions(
        await as_(world.grace)("GET", f"/v1/clients/{world.thornbury_client}/activity")
    )
    assert "entity_relationship.created" in grace


async def test_a_client_principal_gets_404(world: World, as_: Callable[[object], Call]) -> None:
    portal = AuthContext(
        tenant=world.grace.tenant,
        user_id=world.grace.user_id,
        membership_id=world.grace.membership_id,
        firm_role=None,
        mfa_at=None,
        client=True,
    )
    response = await as_(portal)("GET", f"/v1/clients/{world.thornbury_client}/activity")
    assert response.status_code == 404
