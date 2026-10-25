"""Q-01-T45 against Postgres and a real Temporal server (ADR-156, P-65; SPEC-050 AC-27; platform-
ops contract sections 3.5 and 3.6): "Re-running a provision with the same key returns the same
tenant, a non-US region is refused, and the audit trail names the operator on every step."

`provision` calls `provision_firm(...)` as `abacus_ops` and starts `TenantProvisioningWorkflow` on
the background class; a worker in this process runs it with the real activity. `make entitlement`
writes as the owner role, audited as the operator.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import replace
from datetime import timedelta
from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from temporalio.client import Client
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.db.session import configure_engine, dispose_engine
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.modules.platform.api import (
    ACTIVITIES,
    WORKFLOWS,
    IncidentPropagationWorkflow,
    InMemoryTenantKeyOps,
    ProvisionTenantResult,
    SpendAnomalyWorkflow,
    TenantKeyWorkflow,
    TenantProvisioningWorkflow,
    configure_tenant_key_ops,
    entitlement,
    operator_context,
    provisioning_workflow_id,
)
from abacus.modules.platform.provisioning import invite_admins, set_plan_entitlements
from abacus.modules.platform.tenant_keys import (
    create_tenant_key,
    replicate_tenant_key,
    verify_tenant_key,
)
from abacus.modules.platform.workflow_types import ProvisionTenantInput, TenantKeyInput
from abacus_tools import tenants
from abacus_tools.tenants import ProvisionRequest, Refused

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

OPERATOR = "probe-op"
QUEUE = f"t45-{uuid.uuid4().hex[:8]}"


def _ops_url(db: MigratedDatabase) -> str:
    # bootstrap-local.sql gives abacus_ops the local password; the role has EXECUTE only.
    return db.app_url.replace("abacus_app:abacusapp", "abacus_ops:abacusops", 1)


def _request(key: str, *, name: str = "Canary & Co", operator: str = OPERATOR) -> ProvisionRequest:
    return ProvisionRequest(
        name=name,
        slug="canary-co",
        synthetic=True,
        plan="pilot",
        admins=("admin@sink.example.test",),
        idempotency_key=key,
        operator=operator,
    )


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
async def temporal(temporal_target: str) -> AsyncIterator[Client]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    yield client
    configure_temporal_client(None)


@pytest.fixture
def key_ops() -> Iterator[InMemoryTenantKeyOps]:
    ops = InMemoryTenantKeyOps()
    configure_tenant_key_ops(ops)
    yield ops
    configure_tenant_key_ops(None)


@pytest.fixture
async def worker(temporal: Client, key_ops: InMemoryTenantKeyOps) -> AsyncIterator[None]:
    assert {
        TenantProvisioningWorkflow: "background",
        TenantKeyWorkflow: "keyops",
        IncidentPropagationWorkflow: "time_sensitive",  # Q-02-T33's register (platform's own)
        SpendAnomalyWorkflow: "background",  # Q-01-T26: on its Schedule, not a worker loop
    } == WORKFLOWS
    activities = cast("list[Callable[..., object]]", list(ACTIVITIES))
    # Two pools, as in production: the general one and the keyops one (P-65).
    async with (
        Worker(
            temporal,
            task_queue=queue_for("background"),
            workflows=list(WORKFLOWS),
            activities=activities,
        ),
        Worker(
            temporal,
            task_queue=queue_for("keyops"),
            workflows=list(WORKFLOWS),
            activities=activities,
        ),
    ):
        yield


async def _finished(temporal: Client, tenant: uuid.UUID) -> ProvisionTenantResult:
    handle = temporal.get_workflow_handle(
        provisioning_workflow_id(str(tenant)), result_type=ProvisionTenantResult
    )
    return await handle.result(rpc_timeout=timedelta(seconds=60))


async def _audit(seed: Seeder, tenant: uuid.UUID) -> list[tuple[str, str, str]]:
    rows = await seed.rows(
        "SELECT actor_kind, actor_id, action FROM audit_events WHERE tenant_id = $1 "
        "ORDER BY occurred_at",
        tenant,
    )
    return [(r["actor_kind"], r["actor_id"], r["action"]) for r in rows]


@pytest.mark.usefixtures("worker")
async def test_ac_rerunning_a_provision_with_the_same_key_returns_the_same_tenant(
    migrated_db: MigratedDatabase, seed: Seeder, temporal: Client
) -> None:
    key = f"provision-{uuid.uuid4().hex}"
    first = await tenants.provision(_ops_url(migrated_db), _request(key))
    assert first.already_provisioned is False
    assert first.workflow_id == f"tenant_provision:{first.tenant_id}"
    result = await _finished(temporal, first.tenant_id)
    # 0107: "pilot" holds no modules here (0 rows); its one first administrator is invited.
    # Q-01-T27: the key runs beside provisioning on the keyops queue, so its status at this point
    # depends on timing; the key's own tests pin each step.
    assert (result.tenant_id, result.entitlement_rows, result.invitations_sent) == (
        str(first.tenant_id),
        0,
        1,
    )
    assert result.key_status in {"none", "active", "replica_verified"}

    again = await tenants.provision(_ops_url(migrated_db), _request(key))
    assert again.tenant_id == first.tenant_id
    assert again.already_provisioned is True  # no second workflow
    firms = await seed.value("SELECT count(*) FROM firms WHERE tenant_id = $1", first.tenant_id)
    assert firms == 1
    outbox = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'tenant.provisioned'",
        first.tenant_id,
    )
    assert len(outbox) == 1
    raw = outbox[0]["payload"]
    payload = json.loads(raw) if isinstance(raw, str) else raw
    assert {k: payload[k] for k in ("tenant_id", "plan", "synthetic", "operator")} == {
        "tenant_id": str(first.tenant_id),
        "plan": "pilot",
        "synthetic": True,
        "operator": OPERATOR,
    }
    assert "admin@sink.example.test" not in str(raw)  # no address in events


@pytest.mark.usefixtures("worker")
async def test_ac_the_audit_trail_names_the_operator_on_every_step(
    migrated_db: MigratedDatabase, seed: Seeder, temporal: Client
) -> None:
    key = f"provision-{uuid.uuid4().hex}"
    outcome = await tenants.provision(_ops_url(migrated_db), _request(key))
    await _finished(temporal, outcome.tenant_id)
    request = await seed.rows(
        "SELECT tenant_id, operator FROM firm_provisioning_requests WHERE idempotency_key = $1",
        key,
    )
    assert [(r["tenant_id"], r["operator"]) for r in request] == [(outcome.tenant_id, OPERATOR)]
    await tenants.set_entitlement(
        migrated_db.owner_url,
        firm=outcome.tenant_id,
        module="attest",
        enabled=True,
        seats=10,
        operator=OPERATOR,
        reason="pilot plan",
    )
    trail = await _audit(seed, outcome.tenant_id)
    # The key's own rows (Q-01-T27) run beside provisioning, on the keyops queue, so they
    # interleave by timing; the provisioning steps keep their order.
    assert [action for _, _, action in trail if action != "tenant_key.recorded"] == [
        "tenant.entitlements_changed",  # the plan's (0107)
        "staff_invitation.issued",  # the first administrator (0107)
        "retention_policy.defaults_applied",  # the published defaults, every run (Q-02-T23)
        "tenant.provisioned",
        "tenant.entitlements_changed",  # the operator's `make entitlement`
    ]
    assert {(kind, actor) for kind, actor, _ in trail} == {("system", f"operator:{OPERATOR}")}


async def test_ac_a_non_us_region_is_refused_and_nothing_is_written(
    migrated_db: MigratedDatabase, seed: Seeder
) -> None:
    key = f"provision-{uuid.uuid4().hex}"
    with pytest.raises(Refused, match="not offered"):
        await tenants.create_firm(
            _ops_url(migrated_db), _request(key, name="Elsewhere LLP"), region="eu"
        )
    assert await seed.value("SELECT count(*) FROM firms WHERE name = 'Elsewhere LLP'") == 0
    assert (
        await seed.value(
            "SELECT count(*) FROM firm_provisioning_requests WHERE idempotency_key = $1", key
        )
        == 0
    )


def test_ac_the_command_line_has_no_region_argument() -> None:
    with pytest.raises(SystemExit):
        tenants.main(
            [
                "provision",
                "--name",
                "Elsewhere LLP",
                "--slug",
                "elsewhere",
                "--plan",
                "pilot",
                "--admins",
                "admin@sink.example.test",
                "--idempotency-key",
                "provision-elsewhere-1",
                "--operator",
                OPERATOR,
                "--region",
                "eu",
            ]
        )


async def test_an_email_address_is_not_an_operator_handle(
    migrated_db: MigratedDatabase, seed: Seeder
) -> None:
    key = f"provision-{uuid.uuid4().hex}"
    with pytest.raises(Refused, match="handle"):
        await tenants.provision(
            _ops_url(migrated_db), _request(key, operator="someone@firm.example.test")
        )
    assert (
        await seed.value(
            "SELECT count(*) FROM firm_provisioning_requests WHERE idempotency_key = $1", key
        )
        == 0
    )


async def test_entitlements_change_as_the_operator_and_status_reports_them(
    migrated_db: MigratedDatabase,
) -> None:
    tenant = await tenants.create_firm(
        _ops_url(migrated_db), _request(f"provision-{uuid.uuid4().hex}")
    )
    for enabled, seats in ((True, 5), (False, 5)):
        await tenants.set_entitlement(
            migrated_db.owner_url,
            firm=tenant,
            module="insights",
            enabled=enabled,
            seats=seats,
            operator=OPERATOR,
            reason="pilot plan",
        )
        held = await entitlement(operator_context(tenant, OPERATOR), "insights")
        assert (held is not None) is enabled
    await tenants.set_entitlement(
        migrated_db.owner_url,
        firm=tenant,
        module="attest",
        enabled=True,
        seats=3,
        operator=OPERATOR,
        reason="pilot plan",
    )
    found = await tenants.status(tenant, with_workflow=False)
    assert found == {
        "tenant_id": str(tenant),
        "synthetic": True,
        "region": "us",
        "key_status": "none",
        "key_ready": False,
        "entitlements": {"attest": 3},
        "workflow": None,
    }


async def test_an_entitlement_for_an_unknown_firm_is_refused(
    migrated_db: MigratedDatabase,
) -> None:
    with pytest.raises(Refused, match="no such firm"):
        await tenants.set_entitlement(
            migrated_db.owner_url,
            firm=uuid.uuid4(),
            module="attest",
            enabled=True,
            seats=None,
            operator=OPERATOR,
            reason="pilot plan",
        )


# --- 0107: the plan's entitlements and the first administrators' invitations ------------------


async def _plan(seed: Seeder, migrated_db: MigratedDatabase) -> str:
    code = f"plan_{uuid.uuid4().hex[:10]}"
    await seed.run("INSERT INTO plans (code, name) VALUES ($1, 'Probe plan')", code)
    for module, seats in (("attest", 12), ("insights", None)):
        await tenants.set_plan_module(
            _ops_url(migrated_db),
            plan=code,
            module=module,
            seats=seats,
            minutes=None,
            operator=OPERATOR,
        )
    return code


@pytest.mark.usefixtures("worker")
async def test_q01t45_a_new_firm_gets_its_plans_entitlements_and_first_admin_invitations(
    migrated_db: MigratedDatabase, seed: Seeder, temporal: Client
) -> None:
    plan = await _plan(seed, migrated_db)
    request = replace(
        _request(f"provision-{uuid.uuid4().hex}"),
        plan=plan,
        admins=("first.admin@sink.example.test", "second.admin@sink.example.test"),
    )
    outcome = await tenants.provision(_ops_url(migrated_db), request)
    result = await _finished(temporal, outcome.tenant_id)
    assert (result.entitlement_rows, result.invitations_sent) == (2, 2)
    held = await seed.rows(
        "SELECT module, seats, plan_code, set_by FROM tenant_entitlements WHERE tenant_id = $1 "
        "ORDER BY module",
        outcome.tenant_id,
    )
    assert [(r["module"], r["seats"], r["plan_code"]) for r in held] == [
        ("attest", 12, plan),
        ("insights", None, plan),
    ]
    assert {r["set_by"] for r in held} == {f"operator:{OPERATOR}"}
    invited = await seed.rows(
        "SELECT email, firm_role, invited_by, issued_by_operator FROM staff_invitations "
        "WHERE tenant_id = $1 ORDER BY email",
        outcome.tenant_id,
    )
    assert [(r["email"], r["firm_role"], r["invited_by"]) for r in invited] == [
        ("first.admin@sink.example.test", "firm_admin", None),
        ("second.admin@sink.example.test", "firm_admin", None),
    ]
    assert {r["issued_by_operator"] for r in invited} == {f"operator:{OPERATOR}"}
    events = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'staff_invitation.issued'",
        outcome.tenant_id,
    )
    assert events == 2


async def test_q01t45_the_writers_refuse_anything_but_a_new_firm(
    migrated_db: MigratedDatabase, seed: Seeder
) -> None:
    unprovisioned = await seed.firm()
    with pytest.raises(DBAPIError, match="was not provisioned"):
        await _as_app(
            unprovisioned, "SELECT apply_plan_entitlements(:tenant, 'pilot', 'operator:probe-op')"
        )
    staffed = await seed.firm()
    await seed.person(staffed)  # an active member: no more operator-issued admin invitations
    with pytest.raises(DBAPIError, match="already has members"):
        await _as_app(
            staffed,
            "SELECT invite_first_admin(:tenant, 'late@sink.example.test', 'operator:probe-op')",
        )


async def _as_app(tenant: uuid.UUID, sql: str) -> None:
    async with tenant_session(TenantContext(tenant, "system", "operator:probe-op")) as session:
        await session.execute(text(sql), {"tenant": tenant})


async def test_q01t45_a_retried_step_writes_nothing_twice(
    migrated_db: MigratedDatabase, seed: Seeder
) -> None:
    plan = await _plan(seed, migrated_db)
    tenant = await tenants.create_firm(
        _ops_url(migrated_db), _request(f"provision-{uuid.uuid4().hex}")
    )
    given = ProvisionTenantInput(
        tenant_id=str(tenant),
        slug="canary-co",
        synthetic=True,
        plan=plan,
        admins=("only.admin@sink.example.test",),
        idempotency_key="x" * 12,
        operator=OPERATOR,
    )
    assert await set_plan_entitlements(given) == 2
    assert await set_plan_entitlements(given) == 0
    assert await invite_admins(given) == 1
    assert await invite_admins(given) == 1
    count = await seed.value("SELECT count(*) FROM staff_invitations WHERE tenant_id = $1", tenant)
    assert count == 1


# --- Q-01-T27: the tenant key, on the keyops queue ----------------------------------------------


async def _key_done(temporal: Client, tenant: uuid.UUID) -> str:
    handle = temporal.get_workflow_handle(f"tenant_key:{tenant}", result_type=str)
    return await handle.result(rpc_timeout=timedelta(seconds=60))


@pytest.mark.usefixtures("worker")
async def test_q01t27_a_new_firm_gets_a_verified_key_in_both_regions(
    migrated_db: MigratedDatabase, seed: Seeder, temporal: Client, key_ops: InMemoryTenantKeyOps
) -> None:
    outcome = await tenants.provision(
        _ops_url(migrated_db), _request(f"provision-{uuid.uuid4().hex}")
    )
    await _finished(temporal, outcome.tenant_id)
    assert await _key_done(temporal, outcome.tenant_id) == "replica_verified"
    row = await seed.rows(
        "SELECT kms_key_arn, kms_key_status, kms_replica_verified_at FROM firms "
        "WHERE tenant_id = $1",
        outcome.tenant_id,
    )
    assert row[0]["kms_key_status"] == "replica_verified"
    assert row[0]["kms_key_arn"] == key_ops.keys[outcome.tenant_id]
    assert row[0]["kms_replica_verified_at"] is not None
    assert outcome.tenant_id in key_ops.replicas
    trail = [action for _, _, action in await _audit(seed, outcome.tenant_id)]
    assert trail.count("tenant_key.recorded") == 2  # active, then replica_verified


async def test_q01t27_an_unverified_replica_leaves_the_firm_active_not_verified(
    migrated_db: MigratedDatabase, seed: Seeder, key_ops: InMemoryTenantKeyOps
) -> None:
    tenant = await tenants.create_firm(
        _ops_url(migrated_db), _request(f"provision-{uuid.uuid4().hex}")
    )
    key_ops.broken_replica.add(tenant)
    given = TenantKeyInput(str(tenant), OPERATOR)
    arn = await create_tenant_key(given)
    replica = await replicate_tenant_key(given, arn)
    with pytest.raises(ApplicationError, match="ReplicaNotVerified"):
        await verify_tenant_key(given, arn, replica)
    status = await seed.value("SELECT kms_key_status FROM firms WHERE tenant_id = $1", tenant)
    assert status == "active"  # ADR-156: no client content until replica_verified
    assert await create_tenant_key(given) == arn  # a retried create reuses the key
