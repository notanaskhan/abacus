"""W-01-T18 (TASK-8357; ADR-078): SPEC-659 AC-27 to AC-30 against Postgres, written outside the
implementing sessions. ac-test-author: ayushkbhatia

- AC-27: a health transition writes its install's status, one `integration_events` row and one
  `integration.health_changed` outbox event; a probe that changes nothing writes nothing.
- AC-28: `connection_needs_reauth` reaches each security and firm admin once, and nobody for a
  move to anything but Needs reauth.
- AC-29: run admission refuses with the first required integration's code (DEC-5320: Needs reauth
  `integration_reauth_required`, needs attention `integration_unhealthy`, anything else, paused
  included, `integration_not_connected`).
- AC-30: the monitor is silent for a firm with `integrations.health_monitor` off; on, a scripted
  refused token moves the install to Needs reauth in one sweep, and a replay changes nothing.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.modules.integrations import connect_service as svc
from abacus.modules.integrations.dependents import admit
from abacus.modules.integrations.fakes import reset_scripts, script_health
from abacus.modules.integrations.health import apply_probe
from abacus.modules.integrations.health_workflow import probe_tenant
from abacus.modules.notifications.catalogue import (
    _reauth_admins,  # pyright: ignore[reportPrivateUsage] -- the kind's recipient rule
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_w01t08_connect import (
    _firm,  # pyright: ignore[reportPrivateUsage] -- W-01-T08's probe firm
    _person,  # pyright: ignore[reportPrivateUsage] -- W-01-T08's probe person
    _state,  # pyright: ignore[reportPrivateUsage] -- W-01-T08's OAuth state reader
)
from .test_w01t08_connect import db as db
from .test_w01t08_connect import fakes_on as fakes_on

pytestmark = pytest.mark.usefixtures("fakes_on")
AT = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean() -> object:
    reset_scripts()
    forget_flags()
    yield None
    reset_scripts()
    forget_flags()


async def _connected(db: MigratedDatabase) -> tuple[uuid.UUID, uuid.UUID]:
    """A synthetic firm with Karbon connected by its security admin: (tenant, install)."""
    tenant = await _firm(db)
    felix = await _person(db, tenant, "security_admin")
    started = await svc.start_firm(felix, "karbon")
    await svc.complete(felix, _state(started.authorise_url), "c")
    seed = Seeder(db.superuser_dsn)
    install = await seed.value(
        "SELECT id FROM firm_integrations WHERE tenant_id = $1 AND catalog_key = 'karbon'", tenant
    )
    assert isinstance(install, uuid.UUID)
    return tenant, install


async def _counts(db: MigratedDatabase, tenant: uuid.UUID) -> tuple[str, int, int]:
    seed = Seeder(db.superuser_dsn)
    status = await seed.value(
        "SELECT status FROM firm_integrations WHERE tenant_id = $1 AND catalog_key = 'karbon'",
        tenant,
    )
    events = await seed.value(
        "SELECT count(*) FROM integration_events WHERE tenant_id = $1 AND kind = 'token_expired'",
        tenant,
    )
    outbox = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'integration.health_changed'",
        tenant,
    )
    return str(status), int(str(events)), int(str(outbox))


async def test_ac27_a_transition_writes_status_event_and_outbox_once(db: MigratedDatabase) -> None:
    tenant, install = await _connected(db)
    system = TenantContext(tenant, "system", "test.health")
    step = await apply_probe(system, install, "unauthorized", failures=0, at=AT, http_status=401)
    assert step.status == "needs_reauth"
    assert await _counts(db, tenant) == ("needs_reauth", 1, 1)
    again = await apply_probe(system, install, "unauthorized", failures=0, at=AT)
    assert again.event is None
    assert await _counts(db, tenant) == ("needs_reauth", 1, 1)  # nothing more


async def test_ac28_needs_reauth_reaches_each_admin_once_and_nothing_else_does(
    db: MigratedDatabase,
) -> None:
    tenant = await _firm(db)
    felix = await _person(db, tenant, "security_admin")
    grace = await _person(db, tenant, "firm_admin")
    await _person(db, tenant, None)  # a member with no admin role hears nothing
    to = await _reauth_admins(tenant, {"to_status": "needs_reauth"})
    assert sorted(to, key=str) == sorted([felix.user_id, grace.user_id], key=str)
    assert len(to) == len(set(to))
    for other in ("needs_attention", "connected", "paused"):
        assert await _reauth_admins(tenant, {"to_status": other}) == []


async def test_ac29_admission_refuses_with_the_first_unconnected_code(
    db: MigratedDatabase,
) -> None:
    tenant, install = await _connected(db)
    system = TenantContext(tenant, "system", "test.health")
    assert await admit(system, ["karbon"]) is None
    assert await admit(system, []) is None
    assert await admit(system, ["box"]) == ("box", "integration_not_connected")
    await apply_probe(system, install, "server_error", failures=2, at=AT)
    assert await admit(system, ["karbon"]) == ("karbon", "integration_unhealthy")
    await apply_probe(system, install, "unauthorized", failures=0, at=AT)
    assert await admit(system, ["karbon", "box"]) == ("karbon", "integration_reauth_required")
    seed = Seeder(db.superuser_dsn)
    await seed.run("UPDATE firm_integrations SET status = 'paused' WHERE id = $1", install)
    assert await admit(system, ["karbon"]) == ("karbon", "integration_not_connected")


async def test_ac30_the_monitor_is_silent_with_its_flag_off_and_replays_once_on(
    db: MigratedDatabase,
) -> None:
    tenant, _ = await _connected(db)
    script_health("karbon", ["unauthorised"])
    assert await probe_tenant(tenant) == 0  # the flag's default is off
    assert await _counts(db, tenant) == ("connected", 0, 0)
    seed = Seeder(db.superuser_dsn)
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'integrations.health_monitor', 'true', 'test-seed', 'TASK-8357')",
        tenant,
    )
    forget_flags()
    assert await probe_tenant(tenant) == 1
    assert await _counts(db, tenant) == ("needs_reauth", 1, 1)
    assert await probe_tenant(tenant) == 0  # Needs reauth is not probed again (replay)
    assert await _counts(db, tenant) == ("needs_reauth", 1, 1)
