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
from collections.abc import AsyncIterator, Callable
from datetime import timedelta
from typing import cast

import pytest
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.config import settings
from abacus.kernel.db.session import configure_engine, dispose_engine
from abacus.kernel.dispatch import queue_for
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.modules.platform.api import (
    ACTIVITIES,
    WORKFLOWS,
    ProvisionTenantResult,
    TenantProvisioningWorkflow,
    entitlement,
    operator_context,
    provisioning_workflow_id,
)
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
async def worker(temporal: Client) -> AsyncIterator[None]:
    assert {TenantProvisioningWorkflow: "background"} == WORKFLOWS
    async with Worker(
        temporal,
        task_queue=queue_for("background"),
        workflows=list(WORKFLOWS),
        activities=cast("list[Callable[..., object]]", list(ACTIVITIES)),
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
    assert result == ProvisionTenantResult(str(first.tenant_id), "none", 0, 0)

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
    assert [action for _, _, action in trail] == [
        "tenant.provisioned",
        "tenant.entitlements_changed",
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
