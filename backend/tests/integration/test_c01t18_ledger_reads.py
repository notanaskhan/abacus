"""C-01-T18 (TASK-8106; SPEC-655 F5, F6, F9) against Postgres: C9 v2.1 served.

Row acceptance: "The account tree foots for July and August, a register page never exceeds 200
rows, and a ledger_line citation verifies against the snapshot it names." Months are recorded
through `record_month_snapshot` (C-01-T17's writer), as the sync would.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Target, uow
from abacus.modules.evidence.citations.ledger_line import verify_ledger_line
from abacus.modules.evidence.citations.registry import Anchor, CitationClaim
from abacus.modules.identity.api import AuthContext
from abacus.modules.ledger import cas_contract, cas_reads
from abacus.modules.ledger.month_ledger import (
    MonthAccount,
    MonthRegisterLine,
    record_month_snapshot,
)
from abacus.modules.ledger.normalise import LedgerLine, NormalisedTrialBalance

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

ACCOUNTS = (
    MonthAccount(
        "35", "1000", "Operating", "asset", "Bank", "Checking", None, "••4417", False, True
    ),
    MonthAccount("80", "2100", "Card", "liability", "Credit Card", None, None, None, False, True),
    MonthAccount("90", "3000", "Owner equity", "equity", "Equity", None, None, None, False, True),
    MonthAccount("40", "4000", "Sales", "income", "Income", None, None, None, False, True),
    MonthAccount("60", "6100", "Repairs", "expense", "Expense", None, None, None, False, True),
)


def _tb(
    period: str, cash: str, card: str, equity: str, sales: str, repairs: str
) -> NormalisedTrialBalance:
    year, month = int(period[:4]), int(period[5:])
    start = date(year, month, 1)
    end = date(year, month, 31 if month in (1, 3, 5, 7, 8, 10, 12) else 30)
    d = Decimal
    lines = (
        LedgerLine("35", "Operating", d(cash), d(0), "35"),
        LedgerLine("80", "Card", d(0), d(card), "80"),
        LedgerLine("90", "Owner equity", d(0), d(equity), "90"),
        LedgerLine("40", "Sales", d(0), d(sales), "40"),
        LedgerLine("60", "Repairs", d(repairs), d(0), "60"),
    )
    debit = d(cash) + d(repairs)
    return NormalisedTrialBalance(start, end, "USD", lines, debit, debit)


def _register(period: str, rows: int, amount: str) -> list[MonthRegisterLine]:
    year, month = int(period[:4]), int(period[5:])
    out: list[MonthRegisterLine] = []
    for n in range(rows):
        day = date(year, month, 1 + n % 28)
        out.append(
            MonthRegisterLine(
                f"e{n}",
                "60",
                f"t{n}",
                day,
                "Expense",
                None,
                "Valley Supply",
                "parts",
                "80",
                Decimal(amount),
            )
        )
        out.append(
            MonthRegisterLine(
                f"c{n}",
                "80",
                f"t{n}",
                day,
                "Expense",
                None,
                "Valley Supply",
                "parts",
                "60",
                Decimal(amount),
            )
        )
    return out


@pytest.fixture
async def seeded(
    migrated_db: MigratedDatabase,
) -> AsyncIterator[tuple[Seeder, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID]]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    partner = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) VALUES "
                "('https://probe.test', $1, $2, 'Priya Raman') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@example.test",
            )
        )
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
        tenant,
        partner,
    )
    client = await seed.value(
        "INSERT INTO clients (tenant_id, name) VALUES ($1, 'Copperleaf') RETURNING id", tenant
    )
    entity = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, "
                "'Copperleaf') "
                "RETURNING id",
                tenant,
                client,
            )
        )
    )
    engagement = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
                "fiscal_period_start, fiscal_period_end, created_by, type, status) VALUES ($1, "
                "$2, $3, "
                "'2026 Close', '2026-01-01', '2026-12-31', $4, 'cas_monthly_close', 'active') "
                "RETURNING id",
                tenant,
                client,
                entity,
                partner,
            )
        )
    )
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'engagement_partner')",
        tenant,
        engagement,
        partner,
    )
    yield seed, tenant, entity, engagement, partner
    await dispose_engine()


async def _record(
    tenant: uuid.UUID,
    entity: uuid.UUID,
    period: str,
    tb: NormalisedTrialBalance,
    rows: int,
    amount: str,
) -> uuid.UUID:
    system = TenantContext(tenant, "system", "connections:ledger_sync")
    async with uow(system) as tx:
        ref = await record_month_snapshot(
            tx,
            client_entity_id=entity,
            period=period,
            tb=tb,
            accounts=ACCOUNTS,
            register=_register(period, rows, amount),
            pulled_at=datetime(2026, 9, 8, 15, tzinfo=UTC),
            source=f"quickbooks_online:{period}",
        )
    return ref.id


async def test_ac_the_tree_foots_for_july_and_august(
    seeded: tuple[Seeder, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    _, tenant, entity, _, _ = seeded
    # July: cash 50,000 = card 4,000 + equity 40,000 + (sales 9,000 - repairs 3,000).
    await _record(
        tenant,
        entity,
        "2026-07",
        _tb("2026-07", "50000.00", "4000.00", "40000.00", "9000.00", "3000.00"),
        3,
        "1000.00",
    )
    await _record(
        tenant,
        entity,
        "2026-08",
        _tb("2026-08", "53500.00", "6560.00", "40000.00", "12500.00", "5560.00"),
        2,
        "1280.00",
    )
    reader = TenantContext(tenant, "system", "probe")
    for period in ("2026-07", "2026-08"):
        tree = await cas_contract.account_tree(reader, entity, period)
        assert cas_reads.foots(tree.totals), period
        assert len(tree.accounts) == 5
    august = await cas_contract.account_tree(reader, entity, "2026-08")
    activity = {b.external_id: b.activity for b in august.balances}
    assert activity["60"] == Decimal("2560.00")  # Repairs & maintenance +2,560 (CLS-10)
    compared = await cas_contract.compare_periods(reader, entity, "2026-08", "2026-07")
    repairs = next(x for x in compared.lines if x.external_id == "60")
    assert (repairs.prior, repairs.current) == (Decimal("3000.00"), Decimal("5560.00"))
    ties = {t.external_id: t.ties for t in await cas_reads.month_tie(reader, entity, "2026-08")}
    assert ties["60"]  # 2 rows of 1,280 = the TB movement of 2,560


async def test_ac_a_register_page_never_exceeds_200_rows(
    seeded: tuple[Seeder, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    _, tenant, entity, _, _ = seeded
    await _record(
        tenant,
        entity,
        "2026-08",
        _tb("2026-08", "1.00", "451.00", "0.00", "0.00", "450.00"),
        450,
        "1.00",
    )
    reader = TenantContext(tenant, "system", "probe")
    seen: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        rows, cursor = await cas_contract.register_lines(
            reader, entity, "60", "2026-08", cursor=cursor
        )
        assert len(rows) <= cas_reads.REGISTER_PAGE
        seen += [r.line_ref for r in rows]
        pages += 1
        if cursor is None:
            break
    assert (len(seen), pages, len(set(seen))) == (450, 3, 450)


async def test_ac_a_register_citation_verifies_against_its_snapshot(
    seeded: tuple[Seeder, uuid.UUID, uuid.UUID, uuid.UUID, uuid.UUID],
) -> None:
    _, tenant, entity, engagement, partner = seeded
    snapshot = await _record(
        tenant,
        entity,
        "2026-08",
        _tb("2026-08", "1.00", "3.00", "0.00", "0.00", "2.00"),
        2,
        "1.00",
    )
    reader = TenantContext(tenant, "system", "probe")
    rows, _ = await cas_contract.register_lines(reader, entity, "60", "2026-08")
    snap, line = rows[0].line_ref.split(":")
    assert uuid.UUID(snap) == snapshot
    actor = AuthContext(
        TenantContext(tenant, "human", str(partner)),
        partner,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )
    anchor = Anchor("close", uuid.uuid4(), engagement_id=engagement)
    locator = {
        "ledger_snapshot_id": str(snapshot),
        "account_code": "60",
        "register_line": int(line),
    }
    async with uow(actor.tenant) as tx:
        good = await verify_ledger_line(
            tx, actor, CitationClaim("ledger_line", locator, "valley supply", "1.00"), anchor
        )
        wrong_value = await verify_ledger_line(
            tx, actor, CitationClaim("ledger_line", locator, None, "9.00"), anchor
        )
        other_account = await verify_ledger_line(
            tx, actor, CitationClaim("ledger_line", {**locator, "account_code": "80"}), anchor
        )
        tx.record("probe.read", target=Target("ledger_snapshot", snapshot))
    assert good.verified and good.source_version == str(snapshot)
    assert wrong_value.reason == "value_mismatch"
    assert other_account.reason == "cell_not_found"
