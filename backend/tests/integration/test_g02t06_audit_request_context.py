"""G-02-T06 against Postgres (migration 0172; SPEC-349 AC-8, AC-9): a person's request writes its
IP, device, staff session and MFA time on its audit event; agent and system events leave them
null, and the database refuses them there; a cookie that is not the actor's names no session;
UPDATE and DELETE on `audit_events` stay refused; the migration goes up, down and up again on a
private local database (the staging-copy run is a deploy step)."""

from __future__ import annotations

import asyncio
import hashlib
import re
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta

import asyncpg
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_connection
from abacus.kernel.request_context import RequestContext, bound
from abacus.kernel.uow import Target, uow
from abacus.modules.identity.api import AuthContext, current_context
from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


def _parent_of_0172() -> str:
    """0172's `down_revision`, read from the migration, so the test holds wherever the chain puts
    0172 (it follows 0160 on its branch and 0171 once the S9 batch merges)."""
    from pathlib import Path

    [script] = Path(__file__).resolve().parents[2].glob("migrations/versions/0172_*.py")
    found = re.search(r'^down_revision = "(\d{4})"$', script.read_text(), flags=re.M)
    assert found is not None
    return found.group(1)


PARENT_0172 = _parent_of_0172()

CHROME_MAC = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)
COOKIE = "__Host-abacus-session"
IP = "198.51.100.57"
_CONTEXT_COLUMNS = (
    "SELECT host(ip) AS ip, user_agent_family, device_label, session_id, auth_method, mfa_at "
    "FROM audit_events WHERE tenant_id = $1 AND action = $2"
)


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


async def _admin(seed: Seeder, tenant: uuid.UUID, mfa_at: datetime) -> AuthContext:
    user = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        user.user_id,
    )
    return AuthContext(
        TenantContext(tenant, "human", str(user.user_id)),
        user.user_id,
        uuid.uuid4(),
        "firm_admin",
        mfa_at,
    )


async def _session(seed: Seeder, user_id: uuid.UUID, mfa_at: datetime) -> tuple[str, uuid.UUID]:
    cookie = uuid.uuid4().hex
    digest = hashlib.sha256(cookie.encode()).hexdigest()
    session_id = await seed.value(
        "SELECT auth_session_start($1, 'workos', NULL, $2, $3, 1800, 43200)",
        user_id,
        mfa_at,
        digest,
    )
    assert isinstance(session_id, uuid.UUID)
    return cookie, session_id


async def _put_autonomy(ctx: AuthContext, cookie: str | None) -> httpx.Response:
    app = create_app()
    app.dependency_overrides[current_context] = lambda: ctx
    transport = httpx.ASGITransport(app=app, client=(IP, 51515))
    headers = {"User-Agent": CHROME_MAC}
    if cookie is not None:
        headers["Cookie"] = f"{COOKIE}={cookie}"
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.put("/v1/firm/autonomy", json={"level": 0}, headers=headers)


async def test_ac9_a_persons_request_writes_ip_device_session_and_mfa_time(seed: Seeder) -> None:
    tenant = await seed.firm()
    mfa_at = datetime(2026, 9, 14, 14, 1, tzinfo=UTC)
    grace = await _admin(seed, tenant, datetime.now(UTC) - timedelta(minutes=1))
    cookie, session_id = await _session(seed, grace.user_id, mfa_at)
    response = await _put_autonomy(grace, cookie)
    assert response.status_code == 200, response.text
    [row] = await seed.rows(_CONTEXT_COLUMNS, tenant, "autonomy_policy.updated")
    assert row["ip"] == IP
    assert row["user_agent_family"] == "Chrome"
    assert row["device_label"] == "Chrome · macOS"
    assert row["session_id"] == session_id
    assert row["mfa_at"] == mfa_at


async def test_ac9_a_cookie_that_is_not_the_actors_names_no_session(seed: Seeder) -> None:
    tenant = await seed.firm()
    grace = await _admin(seed, tenant, datetime.now(UTC) - timedelta(minutes=1))
    someone = await seed.person(tenant)
    cookie, _ = await _session(seed, someone.user_id, datetime.now(UTC))
    assert (await _put_autonomy(grace, cookie)).status_code == 200
    [row] = await seed.rows(_CONTEXT_COLUMNS, tenant, "autonomy_policy.updated")
    assert row["ip"] == IP
    assert row["session_id"] is None


@pytest.mark.parametrize("kind", ["agent", "system"])
async def test_ac9_agent_and_system_events_leave_the_context_null(seed: Seeder, kind: str) -> None:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    ctx = TenantContext(tenant, kind, f"{kind}:probe", person.user_id if kind == "agent" else None)  # pyright: ignore[reportArgumentType] -- an actor kind code
    with bound(RequestContext(ip=IP, user_agent_family="Chrome", device_label="Chrome · macOS")):
        async with uow(ctx) as tx:
            tx.record("probe.recorded", target=Target("probe", uuid.uuid4()))
    [row] = await seed.rows(_CONTEXT_COLUMNS, tenant, "probe.recorded")
    assert dict(row) == dict.fromkeys(row.keys(), None)


async def test_ac9_a_support_engineers_event_says_support(seed: Seeder) -> None:
    tenant = await seed.firm()
    ctx = TenantContext(tenant, "support", f"support:{uuid.uuid4()}")
    with bound(RequestContext(ip=IP, user_agent_family="Firefox", device_label="Firefox · Linux")):
        async with uow(ctx) as tx:
            tx.record("support.requested", target=Target("probe", uuid.uuid4()))
    [row] = await seed.rows(_CONTEXT_COLUMNS, tenant, "support.requested")
    assert (row["ip"], row["auth_method"], row["device_label"]) == (
        IP,
        "support",
        "Firefox · Linux",
    )


async def test_the_database_refuses_request_context_on_a_system_event(seed: Seeder) -> None:
    tenant = await seed.firm()
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.as_actor(
            tenant,
            ("system", "system:probe"),
            "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, "
            "target_id, ip) VALUES ($1, 'system', 'system:probe', 'probe.recorded', 'probe', "
            "$2, '198.51.100.57')",
            tenant,
            str(uuid.uuid4()),
        )


@pytest.mark.parametrize(
    "statement", ["UPDATE audit_events SET ip = '203.0.113.1'", "DELETE FROM audit_events"]
)
async def test_ac8_update_and_delete_stay_refused_for_the_app(
    seed: Seeder, statement: str
) -> None:
    tenant = await seed.firm()
    with pytest.raises(DBAPIError):
        async with tenant_connection(TenantContext(tenant, "human", str(uuid.uuid4()))) as conn:
            await conn.execute(text(statement))


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def test_migration_0172_goes_up_down_and_up(private_db: sc.Database) -> None:
    columns = (
        "SELECT count(*) FROM information_schema.columns WHERE table_name = 'audit_events' "
        "AND column_name IN ('ip', 'user_agent_family', 'device_label', 'session_id', "
        "'auth_method', 'mfa_at', 'client_id', 'office_id')"
    )

    async def count() -> int:
        return int(str(await Seeder(private_db.superuser_dsn).value(columns)))

    assert asyncio.run(count()) == 8
    migrate(private_db.owner_url, PARENT_0172, down=True)
    assert asyncio.run(count()) == 0
    migrate(private_db.owner_url, "head")
    assert asyncio.run(count()) == 8
    # M3: a failure in the autocommit block leaves alembic at 0160 with the transactional part
    # applied; running the upgrade again finishes it.
    seed = Seeder(private_db.superuser_dsn)
    asyncio.run(seed.run("UPDATE alembic_version SET version_num = $1", PARENT_0172))
    asyncio.run(seed.run("DROP INDEX audit_events_ip"))
    migrate(private_db.owner_url, "head")
    assert asyncio.run(count()) == 8
    indexes = asyncio.run(
        seed.value(
            "SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid = i.indexrelid "
            "WHERE c.relname LIKE 'audit_events_%' AND c.relname IN ('audit_events_feed', "
            "'audit_events_actor_kind', 'audit_events_client', 'audit_events_ip') "
            "AND i.indisvalid"
        )
    )
    assert indexes == 4
