"""C-01-T17 (TASK-8105; SPEC-655 US-5.1, US-5.2) against Postgres: one entity's hourly sync.

Row acceptance: "A recorded history replays (tests/workflows), a changed August register produces
exactly one new snapshot and event, a token_expired failure pauses the entity's sync without a
pull, and freshness stays within 60 +/- 15." The provider is a stub connector (no network); the
Intuit parsers are covered by C-01-T16's tests, so the payloads here are typed directly.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

import abacus.modules.closes.api  # registers the `close` kind and the sync scope
from abacus.kernel import clock
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.closes import service as closes_service
from abacus.modules.connections import ledger_sync
from abacus.modules.connections.connector import ConnectorError, Period, RawPayload
from abacus.modules.evidence.api import StoredObject
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger.month_ledger import MonthAccount, MonthRegisterLine
from abacus.modules.ledger.normalise import LedgerLine, NormalisedTrialBalance

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
assert abacus.modules.closes.api

AT = datetime(2026, 9, 8, 15, 2, tzinfo=UTC)  # Tue Sep 8, 2026, 10:02 AM CDT


class _Stub:
    """A ledger connector with scripted answers; counts calls as the QBO connector does."""

    def __init__(self) -> None:
        self.calls = 0
        self.changed: tuple[str, ...] = ("gl_detail", "trial_balance_month")
        self.fail: str | None = None

    async def changes_since(self, since: datetime) -> Sequence[str]:
        self.calls += 1
        if self.fail:
            raise ConnectorError(self.fail)
        return self.changed

    async def pull(self, dataset: str, period: Period, cursor: str | None) -> RawPayload:
        self.calls += 1
        if self.fail:
            raise ConnectorError(self.fail)
        tag = f"{dataset}:{period.start:%Y-%m}".encode()
        return RawPayload(tag, "application/json", "quickbooks_online", AT, dataset)


REGISTER_AMOUNT = {"2026-07": Decimal("1530.00"), "2026-08": Decimal("2560.00")}


def _tb(payload: RawPayload) -> NormalisedTrialBalance:
    period = payload.content.decode().split(":")[1]
    start = date(int(period[:4]), int(period[5:]), 1)
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    lines = (
        LedgerLine("35", "Operating", Decimal("48210.55"), Decimal(0), "35"),
        LedgerLine("80", "Card", Decimal(0), Decimal("48210.55"), "80"),
    )
    return NormalisedTrialBalance(
        start, end, "USD", lines, Decimal("48210.55"), Decimal("48210.55")
    )


def _accounts(payloads: Sequence[RawPayload]) -> tuple[MonthAccount, ...]:
    return (
        MonthAccount(
            "35", "1000", "Operating", "asset", "Bank", "Checking", None, None, False, True
        ),
        MonthAccount("60", "6100", "Repairs", "expense", "Expense", None, None, None, False, True),
        MonthAccount(
            "80", "2100", "Card", "liability", "Credit Card", None, None, None, False, True
        ),
    )


def _register(payload: RawPayload) -> tuple[MonthRegisterLine, ...]:
    period = payload.content.decode().split(":")[1]
    amount = REGISTER_AMOUNT[period]
    day = date(int(period[:4]), int(period[5:]), 14)
    return (
        MonthRegisterLine("r1", "60", "t-1", day, "Expense", None, "Valley", None, "80", amount),
        MonthRegisterLine("r2", "80", "t-1", day, "Expense", None, "Valley", None, "60", amount),
    )


async def _stored(tenant_id: uuid.UUID, content: bytes) -> StoredObject:
    return StoredObject(f"raw/{uuid.uuid4()}", "v1", "0" * 64, len(content))


class _Firm:
    def __init__(self, seed: Seeder) -> None:
        self.seed = seed
        self.tenant = uuid.uuid4()
        self.partner = uuid.uuid4()

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", self.tenant
        )
        self.partner = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Priya Raman') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
            self.tenant,
            self.partner,
        )
        return self

    def ctx(self) -> AuthContext:
        tenant = TenantContext(self.tenant, "human", str(self.partner))
        return AuthContext(tenant, self.partner, uuid.uuid4(), None, datetime.now(UTC))

    async def copperleaf(self) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        client = await self.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Copperleaf') RETURNING id",
            self.tenant,
        )
        entity = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO client_entities (tenant_id, client_id, name) "
                    "VALUES ($1, $2, 'Copperleaf') RETURNING id",
                    self.tenant,
                    client,
                )
            )
        )
        engagement = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                    "fiscal_period_start, fiscal_period_end, created_by, type, status) "
                    "VALUES ($1, $2, $3, '2026 Close', '2026-01-01', '2026-12-31', $4, "
                    "'cas_monthly_close', 'active') RETURNING id",
                    self.tenant,
                    client,
                    entity,
                    self.partner,
                )
            )
        )
        await self.seed.run(
            "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
            "VALUES ($1, $2, $3, 'engagement_partner')",
            self.tenant,
            engagement,
            self.partner,
        )
        connection = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO connections (tenant_id, client_entity_id, provider, status, "
                    "scopes, created_by, category) VALUES ($1, $2, 'quickbooks_online', 'active', "
                    "'{}', 'probe', 'ledger') RETURNING id",
                    self.tenant,
                    entity,
                )
            )
        )
        return engagement, entity, connection


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> _Stub:
    connector = _Stub()

    async def _on(*_: object, **__: object) -> bool:
        return True

    async def _no_credentials(*_: object) -> None:
        return None

    monkeypatch.setattr(ledger_sync, "flag_enabled", _on)

    def _connector(*_: object) -> object:
        return connector

    monkeypatch.setattr(ledger_sync, "connector_for", _connector)
    monkeypatch.setattr(ledger_sync, "credentials_of", _no_credentials)
    monkeypatch.setattr(ledger_sync, "stage_content", _stored)
    monkeypatch.setattr(ledger_sync, "_tb", _tb)
    monkeypatch.setattr(ledger_sync, "_accounts", _accounts)
    monkeypatch.setattr(ledger_sync, "_register", _register)
    return connector


async def _count(firm: _Firm, sql: str, *args: object) -> int:
    return int(str(await firm.seed.value(sql, *args)))


async def test_ac_first_sync_records_both_open_months(firm: _Firm, stub: _Stub) -> None:
    engagement, entity, connection = await firm.copperleaf()
    await closes_service.generate_closes(firm.ctx(), engagement, 2026)
    with clock.frozen(AT):
        outcome = await ledger_sync.sync_entity(firm.tenant, connection)
    assert outcome.state == "synced"
    assert outcome.snapshots == 2  # July and August: the latest two ended, unlocked months
    months = await _count(
        firm,
        "SELECT count(*) FROM ledger_snapshots WHERE client_entity_id = $1 AND period_kind = "
        "'month'",
        entity,
    )
    assert months == 2
    assert outcome.calls == stub.calls
    meter = await _count(
        firm, "SELECT calls FROM connection_meter_usage WHERE tenant_id = $1", firm.tenant
    )
    assert meter == stub.calls


async def test_ac_a_changed_august_register_records_exactly_one_new_set(
    firm: _Firm, stub: _Stub
) -> None:
    engagement, entity, connection = await firm.copperleaf()
    await closes_service.generate_closes(firm.ctx(), engagement, 2026)
    with clock.frozen(AT):
        await ledger_sync.sync_entity(firm.tenant, connection)
    events_before = await _count(
        firm,
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'change_event.detected'",
        firm.tenant,
    )
    REGISTER_AMOUNT["2026-08"] = Decimal("2570.00")
    try:
        with clock.frozen(AT + timedelta(hours=1)):
            outcome = await ledger_sync.sync_entity(firm.tenant, connection)
    finally:
        REGISTER_AMOUNT["2026-08"] = Decimal("2560.00")
    assert outcome.snapshots == 1  # July is unchanged: its set is found, not written
    august = await _count(
        firm,
        "SELECT count(*) FROM ledger_snapshots WHERE client_entity_id = $1 AND period = '2026-08'",
        entity,
    )
    assert august == 2
    events_after = await _count(
        firm,
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = "
        "'change_event.detected'",
        firm.tenant,
    )
    assert events_after == events_before + 1


async def test_ac_nothing_changed_records_nothing(firm: _Firm, stub: _Stub) -> None:
    engagement, _, connection = await firm.copperleaf()
    await closes_service.generate_closes(firm.ctx(), engagement, 2026)
    with clock.frozen(AT):
        await ledger_sync.sync_entity(firm.tenant, connection)
    stub.changed = ()
    stub.calls = 0
    with clock.frozen(AT + timedelta(hours=1)):
        outcome = await ledger_sync.sync_entity(firm.tenant, connection)
    assert outcome.state == "unchanged"
    assert stub.calls == 1  # the change-data-capture question only


async def test_ac_token_expired_pauses_the_entity_without_a_pull(firm: _Firm, stub: _Stub) -> None:
    engagement, _, connection = await firm.copperleaf()
    await closes_service.generate_closes(firm.ctx(), engagement, 2026)
    with clock.frozen(AT):
        await ledger_sync.sync_entity(firm.tenant, connection)
    stub.fail = "token_expired"
    stub.calls = 0
    with clock.frozen(AT + timedelta(hours=1)):
        outcome = await ledger_sync.sync_entity(firm.tenant, connection)
    assert outcome.state == "needs_reauth"
    assert stub.calls == 1  # the refused question; no dataset is pulled
    paused = await firm.seed.value(
        "SELECT paused_reason FROM sync_schedules WHERE connection_id = $1", connection
    )
    assert paused == "needs_reauth"
    # The next tick leaves before any provider call: the connection now needs its client.
    stub.calls = 0
    with clock.frozen(AT + timedelta(hours=2)):
        again = await ledger_sync.sync_entity(firm.tenant, connection)
    assert again.state == "needs_reauth"
    assert stub.calls == 0


async def test_ac_the_budget_pauses_scheduled_syncs_but_not_sync_now(
    firm: _Firm, stub: _Stub
) -> None:
    engagement, _, connection = await firm.copperleaf()
    await closes_service.generate_closes(firm.ctx(), engagement, 2026)
    await firm.seed.run(
        "INSERT INTO connection_meter_usage (tenant_id, provider, month, calls, budget) "
        "VALUES ($1, 'intuit', '2026-09', 500, 500)",
        firm.tenant,
    )
    with clock.frozen(AT):
        scheduled = await ledger_sync.sync_entity(firm.tenant, connection)
        now = await ledger_sync.sync_entity(firm.tenant, connection, "on_demand", "priya")
    assert (scheduled.state, scheduled.failure_code) == ("paused", "meter_budget_exhausted")
    assert now.state == "synced"


async def test_ac_freshness_is_one_hour_between_ticks(firm: _Firm, stub: _Stub) -> None:
    engagement, _, connection = await firm.copperleaf()
    await closes_service.generate_closes(firm.ctx(), engagement, 2026)
    with clock.frozen(AT):
        await ledger_sync.sync_entity(firm.tenant, connection)
        facts = await ledger_sync.sync_facts(
            TenantContext(firm.tenant, "system", "t"),
            _entity := (
                uuid.UUID(
                    str(
                        await firm.seed.value(
                            "SELECT client_entity_id FROM connections WHERE id = $1", connection
                        )
                    )
                )
            ),
        )
    assert facts.state == "synced"
    assert facts.last_synced_at == AT
    assert facts.next_sync_at is not None
    assert timedelta(minutes=45) <= facts.next_sync_at - AT <= timedelta(minutes=75)
    with clock.frozen(AT):
        plan = await ledger_sync.plan_tick(firm.tenant)
    assert plan.connection_ids == []  # synced this hour: next tick in about an hour
    assert 45 * 60 <= plan.wait_seconds <= 3600
