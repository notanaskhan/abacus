"""Q-02-T33 against Postgres (migration 0143; Q-02 AC-38, AC-39).

The row's acceptance: an incident discovered Sep 10 with 500 or more unencrypted consumers reads
notify by Oct 10, and a propagated Accrued incident appears in each affected firm's register with
Accrued's facts. `IncidentPropagation`'s step is called here as the workflow calls it (its replay
history is in `tests/workflows/`)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from typing import cast

import asyncpg
import pytest
from temporalio import activity
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.dispatch import queue_for
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import forget_flags
from abacus.kernel.temporal import data_converter
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.platform import incidents
from abacus.modules.platform.incidents import (
    ConfirmedOutOfOrder,
    DiscoveredInFuture,
    FirmNotFound,
    IncidentFacts,
)
from abacus.modules.platform.workflow_types import (
    IncidentFactsInput,
    IncidentPropagationInput,
    IncidentPropagationOutcome,
    IncidentPropagationResult,
    IncidentPropagationStep,
    IncidentStepResult,
)

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
        (
            await incidents.propagate_into(
                IncidentPropagationStep(
                    "ACC-2026-007", str(t), _accrued(confirmed), str(staff), "a" * 64
                )
            )
        ).ref
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
    assert (again.ref, again.status) == ("INC-2026-001", "identical")
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

    outcome = await incidents.start_propagation(
        uuid.uuid4(), "ACC-2026-008", [on[0], on[1], on[0]], _accrued(confirmed), "Accrued SEV1"
    )
    assert (outcome.started, outcome.identical) == (on, [])
    (workflow, arg, workflow_id), = started  # fmt: skip
    assert workflow is incidents.IncidentPropagationWorkflow
    assert workflow_id == "incident_propagate:ACC-2026-008"
    assert "Accrued SEV1" not in repr(arg)  # only the reason's fingerprint travels


# --- security review (S7): isolation, changed facts, the system guard, the staff record --------


async def _log(seed: Seeder, ref: str) -> list[asyncpg.Record]:
    return await seed.rows(
        "SELECT event, staff_id, firms, written, identical, failed_tenant_ids, refusal, "
        "reason_sha256 FROM incident_propagations WHERE accrued_ref = $1 ORDER BY id",
        ref,
    )


async def test_review_a_firm_that_keeps_failing_does_not_stop_the_firms_after_it(
    temporal_target: str,
) -> None:
    """Firm 2 of 4 fails every attempt: firms 3 and 4 still get their entries, and the run ends
    with the failed firm named in its result and in the finishing record."""
    firms = [str(uuid.uuid4()) for _ in range(4)]
    finished: list[IncidentPropagationOutcome] = []

    @activity.defn(name="platform.propagate_incident_v2")
    async def step(given: IncidentPropagationStep) -> IncidentStepResult:
        if given.tenant_id == firms[1]:
            raise ApplicationError("OperationalError", type="OperationalError", non_retryable=True)
        return IncidentStepResult(given.tenant_id, "INC-2026-001", "written")

    @activity.defn(name="platform.finish_incident_propagation")
    async def finish(outcome: IncidentPropagationOutcome) -> None:
        finished.append(outcome)

    client = await Client.connect(temporal_target, data_converter=data_converter())
    queue = queue_for("time_sensitive")
    async with Worker(
        client,
        task_queue=queue,
        workflows=[incidents.IncidentPropagationWorkflow],
        activities=[step, finish],
    ):
        result = await client.execute_workflow(
            "IncidentPropagation",
            IncidentPropagationInput(
                "ACC-2026-020",
                tuple(firms),
                _accrued(datetime.now(UTC) - timedelta(hours=1)),
                str(uuid.uuid4()),
                "b" * 64,
            ),
            id=f"test-incident-isolation-{uuid.uuid4().hex}",
            task_queue=queue,
            result_type=IncidentPropagationResult,
        )
    assert result.failed_tenant_ids == (firms[1],)
    assert [r.tenant_id for r in result.written] == [firms[0], firms[2], firms[3]]
    assert len(finished) == 1 and finished[0].failed_tenant_ids == (firms[1],)
    assert finished[0].written == 3


async def test_review_a_repeat_with_changed_facts_is_refused_and_writes_nothing(
    seed: Seeder,
) -> None:
    tenant = await _firm(seed)
    confirmed = datetime.now(UTC) - timedelta(hours=2)
    staff = str(uuid.uuid4())
    first = await incidents.propagate_into(
        IncidentPropagationStep("ACC-2026-021", str(tenant), _accrued(confirmed), staff, "c" * 64)
    )
    assert first.status == "written"
    changed = replace(_accrued(confirmed), consumers_affected=900)
    with pytest.raises(incidents.IncidentFactsChanged):
        await incidents.propagate_into(
            IncidentPropagationStep("ACC-2026-021", str(tenant), changed, staff, "c" * 64)
        )
    rows = await seed.rows(
        "SELECT consumers_affected, facts_sha256 FROM security_incidents WHERE tenant_id = $1",
        tenant,
    )
    assert [r["consumers_affected"] for r in rows] == [0]
    assert rows[0]["facts_sha256"] == incidents.facts_sha256(_accrued(confirmed))


async def test_review_staff_learn_which_firms_were_identical_and_a_changed_repeat_is_409(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[object] = []

    async def fake_dispatch(workflow: type, arg: object, **kwargs: object) -> None:
        started.append(arg)

    monkeypatch.setattr(incidents, "dispatch", fake_dispatch)
    done, fresh = await _firm(seed), await _firm(seed)
    confirmed = datetime.now(UTC) - timedelta(hours=2)
    staff = uuid.uuid4()
    await incidents.propagate_into(
        IncidentPropagationStep(
            "ACC-2026-022", str(done), _accrued(confirmed), str(staff), "d" * 64
        )
    )
    outcome = await incidents.start_propagation(
        staff, "ACC-2026-022", [done, fresh], _accrued(confirmed), "Accrued SEV1"
    )
    assert (outcome.started, outcome.identical) == ([fresh], [done])
    assert len(started) == 1

    changed = replace(_accrued(confirmed), unencrypted=True)
    with pytest.raises(incidents.IncidentFactsChanged) as refused:
        await incidents.start_propagation(
            staff, "ACC-2026-022", [done, fresh], changed, "Accrued SEV1"
        )
    assert refused.value.code == "incident_facts_changed"
    assert len(started) == 1  # nothing started
    log = await _log(seed, "ACC-2026-022")
    assert [(r["event"], r["refusal"]) for r in log] == [
        ("requested", None),
        ("refused", "facts_changed"),
    ]
    assert {r["staff_id"] for r in log} == {staff}
    assert log[0]["firms"] == 2 and log[0]["identical"] == 1
    assert log[0]["reason_sha256"] == incidents.reason_sha256("Accrued SEV1")


async def test_review_a_refused_request_is_recorded_too(seed: Seeder) -> None:
    off = await _firm(seed, flag=False)
    staff = uuid.uuid4()
    with pytest.raises(NotFound):
        await incidents.start_propagation(
            staff, "ACC-2026-023", [off], _accrued(datetime.now(UTC)), "Accrued SEV1"
        )
    log = await _log(seed, "ACC-2026-023")
    assert [(r["event"], r["refusal"], r["firms"]) for r in log] == [
        ("refused", "register_off", 1)
    ]


async def test_review_the_finishing_record_names_the_failed_firms(seed: Seeder) -> None:
    failed = uuid.uuid4()
    await incidents.finish_propagation(
        IncidentPropagationOutcome(
            "ACC-2026-024", str(uuid.uuid4()), "e" * 64, 3, 2, 0, (str(failed),)
        )
    )
    log = await _log(seed, "ACC-2026-024")
    assert [(r["event"], r["written"], r["failed_tenant_ids"]) for r in log] == [
        ("completed", 2, [failed])
    ]
    events = await incidents.propagation_log("ACC-2026-024")
    assert [e.failed_tenant_ids for e in events] == [(failed,)]


async def test_review_only_the_propagation_actor_writes_an_accrued_entry(seed: Seeder) -> None:
    tenant = await _firm(seed)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            tenant,
            ("system", "legal_holds"),
            "INSERT INTO security_incidents (tenant_id, ref, title, event_kind, discovered_at, "
            "ftc_notify_by, source, accrued_ref, accrued_confirmed_at, dpa_notice_at, "
            "facts_sha256) VALUES ($1, 'INC-2026-060', 'x', 'other', now(), current_date, "
            "'accrued', 'ACC-1', now(), now(), repeat('0', 64))",
            tenant,
        )


async def test_review_a_firm_session_cannot_forge_the_staff_record(seed: Seeder) -> None:
    tenant = await _firm(seed)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.as_actor(
            tenant,
            ("system", "incident_propagation"),
            "SELECT record_incident_propagation('ACC-2026-025', 'completed', $1, repeat('0', 64), "
            "NULL, 1, 1, 0, '{}'::uuid[], NULL)",
            uuid.uuid4(),
        )
