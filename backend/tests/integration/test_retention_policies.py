"""Q-02-T23 against Postgres (migration 0112; Q-02 AC-30): a floor publishes only after a second
staff member approves it, saving a policy below its floor is `below_floor`, a locked policy is
never shortened, a firm without a policy reads its floor, every firm gets a policy per published
default (never below the floor) at provisioning and through the ops back-fill, and no floor or
default value is written in the migration."""

from __future__ import annotations

import re
import secrets
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.evidence.retention import (
    BelowFloor,
    PolicyChange,
    PolicyLocked,
    SamePerson,
    effective_policies,
    import_set,
    publish_set,
    set_policy,
)
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.platform.provisioning import apply_retention_defaults
from abacus.modules.platform.workflow_types import ProvisionTenantInput

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

MIGRATION = Path(__file__).parents[2] / "migrations" / "versions" / "0112_retention.py"


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


def _version() -> int:
    return 1_000 + secrets.randbelow(9_000_000)  # global sets: a number no other test uses


def _kind() -> str:
    return f"probe_{uuid.uuid4().hex[:8]}"


async def _admin(seed: Seeder, tenant: uuid.UUID, *, fresh: bool = True) -> AuthContext:
    user = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://probe.test', $1, $2, 'Felix Andersen') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@example.test",
            )
        )
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, 'security_admin', 'active')",
        tenant,
        user,
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=uuid.uuid4(),
        firm_role="security_admin",
        mfa_at=datetime.now(UTC) - (timedelta(minutes=1) if fresh else timedelta(days=2)),
    )


async def _publish_floor(record_type: str, years: str) -> None:
    version = _version()
    await import_set(
        "floors",
        version,
        [
            {
                "record_type": record_type,
                "service_line": "any",
                "legal_floor_years": years,
                "anchor": "report_release",
                "authority": "Probe authority",
            }
        ],
        "staff-a",
    )
    await publish_set("floors", version, "staff-b")


async def test_q02t23_a_floor_publishes_only_on_a_second_persons_approval(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    version, kind = _version(), _kind()
    rows = [
        {
            "record_type": kind,
            "service_line": "audit",
            "legal_floor_years": "7",
            "anchor": "report_release",
            "authority": "Probe authority",
        }
    ]
    assert await import_set("floors", version, rows, "staff-a") == 1
    with pytest.raises(SamePerson):
        await publish_set("floors", version, "staff-a")
    status = await seed.value(
        "SELECT status FROM retention_floors WHERE set_version = $1", version
    )
    assert status == "draft"
    assert await publish_set("floors", version, "staff-b") == 1
    assert (
        await seed.value(
            "SELECT approved_by FROM retention_floors WHERE set_version = $1", version
        )
        == "staff-b"
    )


async def test_q02t23_a_policy_below_its_floor_is_refused_and_a_lock_holds(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    admin = await _admin(seed, tenant)
    kind = _kind()
    await _publish_floor(kind, "7")

    with pytest.raises(BelowFloor):
        await set_policy(admin, PolicyChange(kind, "audit", Decimal("6.5"), "report_release"))
    assert (
        await set_policy(admin, PolicyChange(kind, "audit", Decimal("7"), "report_release")) == 1
    )
    locked = PolicyChange(kind, "audit", Decimal("10"), "report_release", lock=True, basis="SEC")
    assert await set_policy(admin, locked) == 2
    with pytest.raises(PolicyLocked):
        await set_policy(
            admin, PolicyChange(kind, "audit", Decimal("8"), "report_release", lock=True)
        )
    history = await seed.rows(
        "SELECT version, firm_years FROM retention_policy_versions "
        "WHERE tenant_id = $1 AND record_type = $2 ORDER BY version",
        tenant,
        kind,
    )
    assert [(r["version"], r["firm_years"]) for r in history] == [
        (1, Decimal("7.0")),
        (2, Decimal("10.0")),
    ]
    events = await seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 AND action LIKE 'retention%'",
        tenant,
    )
    assert [e["action"] for e in events] == ["retention_policy.updated"] * 2


async def test_q02t23_saving_needs_fresh_mfa(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    stale = await _admin(seed, tenant, fresh=False)
    with pytest.raises(Forbidden):
        await set_policy(stale, PolicyChange(_kind(), "tax", Decimal("7"), "filing_date"))


async def test_q02t23_a_firm_without_a_policy_reads_its_floor(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    admin = await _admin(seed, tenant)
    kind = _kind()
    await _publish_floor(kind, "5")
    [found] = [p for p in await effective_policies(admin) if p.record_type == kind]
    assert found.source == "floor" and found.version is None
    assert found.firm_years == found.legal_floor_years == Decimal("5.0")


async def test_q02t23_defaults_apply_at_provisioning_and_never_below_the_floor(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    floored, plain = _kind(), _kind()
    floors = _version()
    await import_set(
        "floors",
        floors,
        [
            {
                "record_type": floored,
                "service_line": "any",
                "legal_floor_years": "7",
                "anchor": "report_release",
                "authority": "Probe authority",
            }
        ],
        "staff-a",
    )
    await publish_set("floors", floors, "staff-b")
    defaults = _version()
    await import_set(
        "defaults",
        defaults,
        [
            {
                "record_type": floored,
                "service_line": "audit",
                "firm_years": "3",
                "clock_start_event": "report_release",
            },
            {
                "record_type": plain,
                "service_line": "tax",
                "firm_years": "4",
                "clock_start_event": "filing_date",
                "lock": True,
            },
        ],
        "staff-a",
    )
    await publish_set("defaults", defaults, "staff-b")

    given = ProvisionTenantInput(
        tenant_id=str(tenant),
        slug="probe",
        synthetic=True,
        plan="pilot",
        admins=(),
        idempotency_key=f"probe-{uuid.uuid4().hex}",
        operator="probe",
    )
    assert await apply_retention_defaults(given) == 2
    assert await apply_retention_defaults(given) == 0  # a retried activity writes nothing more
    rows = {
        r["record_type"]: r
        for r in await seed.rows(
            "SELECT record_type, firm_years, lock, updated_by FROM retention_policies "
            "WHERE tenant_id = $1",
            tenant,
        )
    }
    assert rows[floored]["firm_years"] == Decimal("7.0")  # raised to the floor
    assert rows[plain]["firm_years"] == Decimal("4.0") and rows[plain]["lock"] is True
    assert rows[plain]["updated_by"] == "system:operator:probe"


async def test_q02t23_the_ops_backfill_reaches_every_platform_firm(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO firm_provisioning_requests (idempotency_key, tenant_id, operator) "
        "VALUES ($1, $2, 'probe')",
        f"probe-{uuid.uuid4().hex}",
        tenant,
    )
    defaults = _version()
    kind = _kind()
    await import_set(
        "defaults",
        defaults,
        [
            {
                "record_type": kind,
                "service_line": "cas",
                "firm_years": "6",
                "clock_start_event": "period_end",
            }
        ],
        "staff-a",
    )
    await publish_set("defaults", defaults, "staff-b")
    result = await seed.rows(
        "SELECT tenant_id, applied FROM retention_defaults_backfill('ops-probe')"
    )
    assert {r["tenant_id"]: r["applied"] for r in result}[tenant] >= 1
    events = await seed.rows(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'retention_policy.defaults_applied'",
        tenant,
    )
    assert [e["actor_id"] for e in events] == ["operator:ops-probe"]


def test_q02t23_no_floor_or_default_value_is_written_in_the_migration() -> None:
    body = MIGRATION.read_text()
    assert not re.search(
        r"INSERT INTO (public\.)?retention_(floors|policy_defaults)[^;]*VALUES", body
    )
    assert not re.search(r"legal_floor_years\s*=\s*\d|firm_years\s*=\s*\d", body)
