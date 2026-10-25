"""Q-01-T52 (ADR-078): acceptance tests for tenant provisioning, the entitlement command, SES
events and the SES identity port (Q-01-T45, T46, T47), from the acceptance text: "Tests pass
unedited and prove idempotency, the region pin, definer-only synthetic flag, abacus_ops holding
no table privileges, and suppression after a simulator bounce."

Each rule is tested as the role that must be held to it, connecting with that role's own
credentials (`abacus_ops`, `abacus_app`), not through the catalogue alone. Same-session
authorship in a solo lane (TASK-1238): independence is nominal; the builder's own tests are
`test_tenant_provisioning.py`, `test_platform_tenancy.py` and `test_message_deliveries.py`."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.communications.api import (
    FakeSesEventQueue,
    FakeSesTransport,
    InMemorySesIdentities,
    SesIdentityInvalid,
    SesIdentityNotFound,
    configure_ses_event_queue,
    drain_ses_events,
    is_suppressed,
    send_email,
)
from abacus.modules.communications.transport import configure_transport

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

PROVISION = "SELECT provision_firm($1, $2, $3, 'America/Chicago', $4, 'probe-op')"


def _as(db: MigratedDatabase, role: str, password: str) -> Seeder:
    """A connection as `role`, with its local password (bootstrap-local.sql)."""
    return Seeder(db.superuser_dsn.replace("postgres:postgres@", f"{role}:{password}@", 1))


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
def ops(migrated_db: MigratedDatabase) -> Seeder:
    return _as(migrated_db, "abacus_ops", "abacusops")


@pytest.fixture
def app(migrated_db: MigratedDatabase) -> Seeder:
    return _as(migrated_db, "abacus_app", "abacusapp")


# --- Idempotency --------------------------------------------------------------------------------


async def test_ac_the_same_idempotency_key_returns_the_same_tenant_and_writes_once(
    ops: Seeder, seed: Seeder
) -> None:
    key = f"t52-{uuid.uuid4().hex}"
    first = await ops.value(PROVISION, "Canary & Co", True, "us", key)
    again = await ops.value(PROVISION, "Canary & Co", True, "us", key)
    assert first == again
    assert await seed.value("SELECT count(*) FROM firms WHERE tenant_id = $1", first) == 1
    requests = await seed.rows(
        "SELECT tenant_id, operator FROM firm_provisioning_requests WHERE idempotency_key = $1",
        key,
    )
    assert [(r["tenant_id"], r["operator"]) for r in requests] == [(first, "probe-op")]


# --- The region pin -----------------------------------------------------------------------------


async def test_ac_a_region_other_than_us_is_refused_and_writes_nothing(
    ops: Seeder, seed: Seeder
) -> None:
    key = f"t52-{uuid.uuid4().hex}"
    with pytest.raises(asyncpg.PostgresError):
        await ops.value(PROVISION, "Elsewhere", True, "eu", key)
    assert (
        await seed.value(
            "SELECT count(*) FROM firm_provisioning_requests WHERE idempotency_key = $1", key
        )
        == 0
    )


async def test_ac_no_role_can_move_a_firm_out_of_the_us(ops: Seeder, seed: Seeder) -> None:
    tenant = await ops.value(PROVISION, "Pinned", True, "us", f"t52-{uuid.uuid4().hex}")
    with pytest.raises(asyncpg.CheckViolationError):  # even the superuser: the CHECK holds
        await seed.run("UPDATE firms SET region = 'eu' WHERE tenant_id = $1", tenant)


# --- The synthetic flag is the definer's alone ---------------------------------------------------


async def test_ac_only_the_definer_sets_the_synthetic_flag(
    ops: Seeder, app: Seeder, seed: Seeder
) -> None:
    tenant = await ops.value(PROVISION, "Synthetic Co", True, "us", f"t52-{uuid.uuid4().hex}")
    real = await ops.value(PROVISION, "Real Co", False, "us", f"t52-{uuid.uuid4().hex}")
    flags = await seed.rows(
        "SELECT tenant_id, synthetic FROM firms WHERE tenant_id = ANY($1::uuid[])", [tenant, real]
    )
    assert {r["tenant_id"]: r["synthetic"] for r in flags} == {tenant: True, real: False}
    for role in (app, ops):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await role.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", real)
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await role.run(
                "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Forged', true)",
                uuid.uuid4(),
            )
    assert await seed.value("SELECT synthetic FROM firms WHERE tenant_id = $1", real) is False


# --- abacus_ops holds no table privileges -----------------------------------------------------


async def test_ac_abacus_ops_holds_no_privilege_on_any_table(seed: Seeder) -> None:
    granted = await seed.rows(
        "SELECT c.relname, p.privilege FROM pg_class c "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "CROSS JOIN unnest(ARRAY['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES',"
        "'TRIGGER']) AS p(privilege) "
        "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm') "
        "AND has_table_privilege('abacus_ops', c.oid, p.privilege)"
    )
    assert [(r["relname"], r["privilege"]) for r in granted] == []


@pytest.mark.parametrize(
    "query",
    [
        "SELECT count(*) FROM firms",
        "SELECT count(*) FROM tenant_entitlements",
        "SELECT count(*) FROM firm_provisioning_requests",
        "SELECT count(*) FROM audit_events",
    ],
)
async def test_ac_abacus_ops_cannot_read_a_table_directly(ops: Seeder, query: str) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await ops.value(query)


# --- Suppression after a simulator bounce ----------------------------------------------------


@pytest.fixture
async def ses(migrated_db: MigratedDatabase, tmp_path: Path) -> AsyncIterator[FakeSesTransport]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    events = FakeSesEventQueue()
    transport = FakeSesTransport(directory=tmp_path, events=events)
    configure_transport(transport)
    configure_ses_event_queue(events)
    yield transport
    configure_transport(None)
    configure_ses_event_queue(None)
    await dispose_engine()
    settings.cache_clear()


async def test_ac_a_simulator_bounce_suppresses_the_next_send(
    ses: FakeSesTransport, ops: Seeder
) -> None:
    tenant = cast(
        uuid.UUID, await ops.value(PROVISION, "Bounce Co", False, "us", f"t52-{uuid.uuid4().hex}")
    )
    address = "bounce@simulator.amazonses.com"
    assert await send_email(
        tenant_id=tenant, message_id=uuid.uuid4(), to=address, subject="Reminder", body="Hello"
    )
    assert len(ses.events) == 1  # the permanent bounce SES would publish
    assert not await is_suppressed(tenant, address)
    assert await drain_ses_events() == 1
    assert len(ses.events) == 0  # recorded and deleted
    assert await is_suppressed(tenant, address)
    assert not await send_email(
        tenant_id=tenant, message_id=uuid.uuid4(), to=address, subject="Again", body="Hello"
    )
    assert len(ses.events) == 0  # nothing was sent, so SES published nothing


async def test_ac_a_delivered_message_suppresses_nothing(
    ses: FakeSesTransport, ops: Seeder
) -> None:
    tenant = cast(
        uuid.UUID,
        await ops.value(PROVISION, "Delivered Co", False, "us", f"t52-{uuid.uuid4().hex}"),
    )
    address = "success@simulator.amazonses.com"
    assert await send_email(
        tenant_id=tenant, message_id=uuid.uuid4(), to=address, subject="Reminder", body="Hello"
    )
    assert await drain_ses_events() == 1
    assert not await is_suppressed(tenant, address)


# --- The SES identity port (T47) ---------------------------------------------------------------


def test_ac_the_identity_port_gives_easy_dkim_and_mail_from_records_and_refuses_bad_hosts() -> (
    None
):
    port = InMemorySesIdentities()
    setup = port.create_identity(domain="mail.example.test", mail_from_subdomain="bounce")
    kinds = sorted({r.type for r in setup.dns_records})
    assert kinds == ["CNAME", "MX", "TXT"]
    assert sum(r.type == "CNAME" for r in setup.dns_records) == 3  # Easy DKIM's three tokens
    assert port.create_identity(domain="mail.example.test", mail_from_subdomain="bounce") == setup
    status = port.identity_status(domain="mail.example.test")
    assert (status.verification, status.dkim, status.mail_from) == ("pending",) * 3
    for bad in ("Mail.Example.test", "mail example.test", "-x.example.test", "example"):
        with pytest.raises(SesIdentityInvalid):
            port.create_identity(domain=bad, mail_from_subdomain="bounce")
    port.delete_identity(domain="mail.example.test")
    with pytest.raises(SesIdentityNotFound):
        port.identity_status(domain="mail.example.test")
