"""A-02-T25 (TASK-1611; A-02 §3.11; DEC-708): the daily connection health pass, on A-02-T16's
world (Tess Moreno's connected ledger), through the migrated test database and row-level security.

The row's acceptance: a fake `token_expired` turns the connection Needs reauth (`needs_attention`
with the reauth reason) with exactly one notification, and no pull runs on a connection that needs
attention. Around it: an outage is `needs_attention` without the reauth event; a healthy check
restores `active`; a reauth due within seven days is told once per due date; the demo ledger and
imports are never probed; one firm's failure does not stop the pass. The workflow's recorded v1
history is added in the batch pass (`tests/workflows/histories/connection-health-v1-checked.json`).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import ClassVar

import pytest

from abacus.kernel.clock import system_now
from abacus.modules.connections import health, service
from abacus.modules.connections.connector import (
    Capabilities,
    Connector,
    ConnectorError,
    Dataset,
    Period,
    RawPayload,
    Unavailable,
)

from . import test_a02t16_entity_connections as t16

World = t16.World
demo_ledger = t16.demo_ledger
no_temporal = t16.no_temporal
world = t16.world

PROBE = "probe_ledger"


class _Probe(Connector):
    """A provider that reaches a host, scripted per test: `fault` None is healthy."""

    provider: ClassVar[str] = PROBE
    fault: ClassVar[ConnectorError | None] = None
    pulls: ClassVar[int] = 0

    def capabilities(self) -> Capabilities:
        return Capabilities(
            frozenset({"trial_balance"}), oauth=True, incremental=False, attachments=False
        )

    async def authorise_url(
        self, state: str, redirect_uri: str, *, code_challenge: str | None = None
    ) -> str:
        return redirect_uri

    async def exchange_code(
        self, code: str, redirect_uri: str, *, code_verifier: str | None = None
    ) -> bytes | None:
        return None

    async def revoke(self) -> None:
        return None

    async def refresh(self) -> None:
        if _Probe.fault is not None:
            raise _Probe.fault

    async def pull(self, dataset: Dataset, period: Period, cursor: str | None) -> RawPayload:
        _Probe.pulls += 1
        raise ConnectorError("no_data")

    async def changes_since(self, since: datetime) -> Sequence[str]:
        return ()

    async def fetch_attachment(self, ref: str) -> RawPayload:
        raise ConnectorError("not_supported")

    async def health(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def probe(monkeypatch: pytest.MonkeyPatch) -> None:
    _Probe.fault = None
    _Probe.pulls = 0
    monkeypatch.setitem(service.CONNECTORS, PROBE, lambda _c, _cred: _Probe())


async def _probed(world: World) -> uuid.UUID:
    done = await world.connected()
    cid = uuid.UUID(str(done["connection_id"]))
    await world.net.seed.run("UPDATE connections SET provider = $2 WHERE id = $1", cid, PROBE)
    return cid


async def _row(world: World, cid: uuid.UUID) -> tuple[str, str | None]:
    rows = await world.net.seed.rows(
        "SELECT status, status_reason_code FROM connections WHERE id = $1", cid
    )
    return rows[0]["status"], rows[0]["status_reason_code"]


async def _events(world: World, event_type: str) -> int:
    return int(
        str(
            await world.net.seed.value(
                "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = $2",
                world.tenant,
                event_type,
            )
        )
    )


async def test_ac_token_expired_needs_reauth_with_exactly_one_notification(world: World) -> None:
    cid = await _probed(world)
    _Probe.fault = ConnectorError("token_expired")
    assert await health.check_firm(world.tenant) == 1
    assert await _row(world, cid) == ("needs_attention", "token_expired")
    assert await health.check_firm(world.tenant) == 1  # the next day: still expired
    assert await _events(world, "connection.needs_reauth") == 1
    actions = await world.net.seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 AND action = "
        "'connection.health_checked'",
        world.tenant,
    )
    assert len(actions) == 2


async def test_ac_no_pull_runs_on_a_connection_that_needs_attention(world: World) -> None:
    cid = await _probed(world)
    _Probe.fault = ConnectorError("token_expired")
    await health.check_firm(world.tenant)
    response = await world.call("POST", f"/v1/portal/connections/{cid}/retry", world.tess)
    assert response.status_code == 409
    assert response.json()["detail"] == "connection_needs_reauth"
    assert _Probe.pulls == 0


async def test_an_outage_needs_attention_without_the_reauth_event(world: World) -> None:
    cid = await _probed(world)
    _Probe.fault = Unavailable("provider_unavailable")
    await health.check_firm(world.tenant)
    assert await _row(world, cid) == ("needs_attention", "provider_unavailable")
    assert await _events(world, "connection.needs_reauth") == 0


async def test_a_healthy_check_restores_active(world: World) -> None:
    cid = await _probed(world)
    _Probe.fault = Unavailable("provider_unavailable")
    await health.check_firm(world.tenant)
    _Probe.fault = None
    await health.check_firm(world.tenant)
    assert await _row(world, cid) == ("active", None)


async def test_a_reauth_due_within_seven_days_is_told_once_per_due_date(world: World) -> None:
    cid = await _probed(world)
    due = system_now() + timedelta(days=3)
    await world.net.seed.run("UPDATE connections SET reauth_due_at = $2 WHERE id = $1", cid, due)
    await health.check_firm(world.tenant)
    await health.check_firm(world.tenant)
    assert await _events(world, "connection.reauth_due") == 1
    await world.net.seed.run(
        "UPDATE connections SET reauth_due_at = $2 WHERE id = $1", cid, due + timedelta(days=1)
    )
    await health.check_firm(world.tenant)
    assert await _events(world, "connection.reauth_due") == 2


async def test_the_demo_ledger_is_never_probed(world: World) -> None:
    await world.connected()  # provider `fake`: networkless
    assert await health.check_firm(world.tenant) == 0


async def test_one_firm_failing_does_not_stop_the_pass(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _probed(world)
    broken = uuid.uuid4()

    async def firms() -> list[uuid.UUID]:
        return [broken, world.tenant]

    async def check(tenant_id: uuid.UUID) -> int:
        if tenant_id == broken:
            raise RuntimeError("boom")
        return await original(tenant_id)

    original = health.check_firm
    monkeypatch.setattr(health, "firm_tenant_ids", firms)
    monkeypatch.setattr(health, "check_firm", check)
    assert await health.check_connection_health() == 1
