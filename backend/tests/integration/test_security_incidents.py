"""Q-02-T33 against Postgres (migration 0143; Q-02 AC-38, AC-39).

The row's acceptance: an incident discovered Sep 10 with 500 or more unencrypted consumers reads
notify by Oct 10, and a propagated Accrued incident appears in each affected firm's register with
Accrued's facts. `IncidentPropagation`'s step is called here as the workflow calls it (its replay
history is in `tests/workflows/`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import cast

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.platform import incidents
from abacus.modules.platform.incidents import (
    ConfirmedOutOfOrder,
    DiscoveredInFuture,
    FirmNotFound,
    IncidentFacts,
)
from abacus.modules.platform.workflow_types import IncidentFactsInput, IncidentPropagationStep

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

SEP_10 = datetime(2026, 9, 10, 14, 5, tzinfo=UTC)


@pytest.fixture(autouse=True)
async def wired(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    forget_flags()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    forget_flags()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _firm(seed: Seeder, *, flag: bool = True) -> uuid.UUID:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET time_zone = 'America/Chicago' WHERE tenant_id = $1", tenant)
    if flag:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, 'compliance.incidents', 'true', 'test-seed', 'Q-02-T33')",
            tenant,
        )
    return tenant


async def _person(
    seed: Seeder, tenant: uuid.UUID, firm_role: str | None = None, level: str | None = None
) -> AuthContext:
    user = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ('https://probe.test', $1, $2, 'Felix Andersen') RETURNING id",
            uuid.uuid4().hex,
            f"{uuid.uuid4().hex}@example.test",
        ),
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level) "
        "VALUES ($1, $2, $3, 'active', $4)",
        tenant,
        user,
        firm_role,
        level,
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


def _facts(consumers: int | None, unencrypted: bool | None) -> IncidentFacts:
    return IncidentFacts(
        title="1,812 failed sign-ins blocked",
        event_kind="credential_attack",
        discovered_at=SEP_10,
        consumers_affected=consumers,
        unencrypted=unencrypted,
    )


async def test_ac38_a_sep_10_incident_of_600_unencrypted_consumers_reads_notify_by_oct_10(
    seed: Seeder,
) -> None:
    tenant = await _firm(seed)
    felix = await _person(seed, tenant, "security_admin")

    view = await incidents.record_incident(felix, _facts(600, True))
    assert view.ref == "INC-2026-001"
    assert view.notification_event is True
    assert view.ftc_notify_by == date(2026, 10, 10)
    assert view.source == "firm" and view.accrued_ref is None and view.dpa_notice_at is None

    under = await incidents.record_incident(felix, _facts(499, True))
    encrypted = await incidents.record_incident(felix, _facts(600, False))
    unknown = await incidents.record_incident(felix, _facts(None, None))
    assert [under.notification_event, encrypted.notification_event] == [False, False]
    assert unknown.notification_event is False
    assert [under.ref, encrypted.ref, unknown.ref] == [
        "INC-2026-002",
        "INC-2026-003",
        "INC-2026-004",
    ]

    rows = await seed.rows(
        "SELECT action, actor_kind, actor_id, target_type FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'incident.recorded' ORDER BY seq",
        tenant,
    )
    assert len(rows) == 4
    assert {(r["actor_kind"], r["actor_id"], r["target_type"]) for r in rows} == {
        ("human", str(felix.user_id), "security_incident")
    }
    outbox = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'incident.recorded'",
        tenant,
    )
    assert len(outbox) == 4


async def test_ac38_only_the_qi_records_and_the_register_is_behind_its_flag(seed: Seeder) -> None:
    tenant = await _firm(seed)
    admin = await _person(seed, tenant, "firm_admin")
    partner = await _person(seed, tenant, level="partner")
    for person in (admin, partner):
        with pytest.raises(Forbidden):
            await incidents.record_incident(person, _facts(600, True))

    off = await _firm(seed, flag=False)
    qi = await _person(seed, off, "security_admin")
    with pytest.raises(NotFound):
        await incidents.record_incident(qi, _facts(600, True))

    felix = await _person(seed, tenant, "security_admin")
    future = IncidentFacts("Later", "other", datetime.now(UTC) + timedelta(days=2), None, None)
    with pytest.raises(DiscoveredInFuture):
        await incidents.record_incident(felix, future)


async def test_ac38_the_database_binds_a_firm_entry_to_its_person_and_is_insert_only(
    seed: Seeder,
) -> None:
    tenant = await _firm(seed)
    felix = await _person(seed, tenant, "security_admin")
    view = await incidents.record_incident(felix, _facts(10, True))
    for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
        granted = await seed.value(
            "SELECT has_table_privilege('abacus_app', 'security_incidents', $1)", privilege
        )
        assert granted is False, privilege
    assert view.ref == "INC-2026-001"
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            tenant,
            ("agent", str(uuid.uuid4())),
            "INSERT INTO security_incidents (tenant_id, ref, title, event_kind, discovered_at, "
            "ftc_notify_by, source, created_by) VALUES ($1, 'INC-2026-099', 'x', 'other', "
            "now(), current_date, 'firm', $2)",
            tenant,
            felix.user_id,
        )


def _accrued(confirmed: datetime) -> IncidentFactsInput:
    return IncidentFactsInput(
        title="Sub-processor credential exposure",
        event_kind="vendor_incident",
        discovered_at=SEP_10.isoformat(),
        consumers_affected=0,
        unencrypted=False,
        confirmed_at=confirmed.isoformat(),
    )


async def test_ac39_an_accrued_incident_reaches_three_firms_with_accrueds_facts_in_72_hours(
    seed: Seeder,
) -> None:
    firms = [await _firm(seed) for _ in range(3)]
    qis = [await _person(seed, t, "security_admin") for t in firms]
    # The first firm already has two incidents of its own: its Accrued entry is its third.
    for _ in range(2):
        await incidents.record_incident(qis[0], _facts(1, True))
    confirmed = datetime.now(UTC) - timedelta(hours=5)
    staff = uuid.uuid4()
    refs = [
        await incidents.propagate_into(
            IncidentPropagationStep(
                "ACC-2026-007", str(t), _accrued(confirmed), str(staff), "a" * 64
            )
        )
        for t in firms
    ]
    assert refs == ["INC-2026-003", "INC-2026-001", "INC-2026-001"]

    for tenant in firms:
        rows = await seed.rows(
            "SELECT title, event_kind, discovered_at, source, accrued_ref, accrued_confirmed_at, "
            "dpa_notice_at, created_by, ftc_notify_by, notification_event "
            "FROM security_incidents WHERE tenant_id = $1 AND source = 'accrued'",
            tenant,
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["title"] == "Sub-processor credential exposure"
        assert (row["event_kind"], row["discovered_at"]) == ("vendor_incident", SEP_10)
        assert (row["accrued_ref"], row["created_by"]) == ("ACC-2026-007", None)
        assert row["accrued_confirmed_at"] == confirmed
        assert timedelta(0) <= row["dpa_notice_at"] - confirmed <= incidents.DPA_NOTICE
        assert row["ftc_notify_by"] == date(2026, 10, 10)
        assert row["notification_event"] is False
        audit = await seed.rows(
            "SELECT actor_kind, after_ref FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'incident.propagated'",
            tenant,
        )
        assert [a["actor_kind"] for a in audit] == ["system"]
        assert str(staff) in str(audit[0]["after_ref"])
        notices = await seed.rows(
            "SELECT event_type FROM outbox WHERE tenant_id = $1 "
            "AND event_type = 'incident.propagated'",
            tenant,
        )
        assert len(notices) == 1

    # Repeat-safe: a retried step writes nothing more and returns the firm's entry.
    again = await incidents.propagate_into(
        IncidentPropagationStep(
            "ACC-2026-007", str(firms[1]), _accrued(confirmed), str(staff), "a" * 64
        )
    )
    assert again == "INC-2026-001"
    count = await seed.value(
        "SELECT count(*) FROM security_incidents WHERE accrued_ref = 'ACC-2026-007'"
    )
    assert count == 3
    with pytest.raises(FirmNotFound):
        await incidents.propagate_into(
            IncidentPropagationStep(
                "ACC-2026-007", str(uuid.uuid4()), _accrued(confirmed), str(staff), "a" * 64
            )
        )


async def test_ac39_only_the_system_writes_an_accrued_entry(seed: Seeder) -> None:
    tenant = await _firm(seed)
    person = await _person(seed, tenant, "security_admin")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            tenant,
            ("human", str(person.user_id)),
            "INSERT INTO security_incidents (tenant_id, ref, title, event_kind, discovered_at, "
            "ftc_notify_by, source, accrued_ref, accrued_confirmed_at, dpa_notice_at) VALUES "
            "($1, 'INC-2026-050', 'x', 'other', now(), current_date, 'accrued', 'ACC-1', now(), "
            "now())",
            tenant,
        )


async def test_ac39_staff_start_only_for_firms_with_the_register_on(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[tuple[type, object, object]] = []

    async def fake_dispatch(workflow: type, arg: object, **kwargs: object) -> None:
        started.append((workflow, arg, kwargs["id"]))

    monkeypatch.setattr(incidents, "dispatch", fake_dispatch)
    on = [await _firm(seed), await _firm(seed)]
    off = await _firm(seed, flag=False)
    confirmed = datetime.now(UTC) - timedelta(hours=1)

    with pytest.raises(NotFound):
        await incidents.start_propagation(
            uuid.uuid4(), "ACC-2026-008", [*on, off], _accrued(confirmed), "Accrued SEV1"
        )
    with pytest.raises(NotFound):
        await incidents.start_propagation(
            uuid.uuid4(), "ACC-2026-008", [uuid.uuid4()], _accrued(confirmed), "Accrued SEV1"
        )
    with pytest.raises(ConfirmedOutOfOrder):
        await incidents.start_propagation(
            uuid.uuid4(),
            "ACC-2026-008",
            on,
            _accrued(SEP_10 - timedelta(days=1)),
            "Accrued SEV1",
        )
    assert started == []

    firms = await incidents.start_propagation(
        uuid.uuid4(), "ACC-2026-008", [on[0], on[1], on[0]], _accrued(confirmed), "Accrued SEV1"
    )
    assert firms == on
    (workflow, arg, workflow_id), = started  # fmt: skip
    assert workflow is incidents.IncidentPropagationWorkflow
    assert workflow_id == "incident_propagate:ACC-2026-008"
    assert "Accrued SEV1" not in repr(arg)  # only the reason's fingerprint travels
