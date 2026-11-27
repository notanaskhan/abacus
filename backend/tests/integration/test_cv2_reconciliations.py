"""CV-2 (TASK-9001; DEC-6003; C-01-T23; CLS-05; DEC-5410) against Postgres: a close's bank
reconciliation as a person works it.

Main CI measured `closes/reconciliations.py` at 34%: the compute engine was proved alone, the
service around it never ran. Here: the first version with no statement is pending; a statement's
version ties with two outstanding items; a changed book balance is a new version that carries the
open item and leaves the cleared one; resolving is once per item; a proposed AJE from an item is
linked; L1 waits while items are open; a ledger snapshot recomputes, and the same inputs make no
version.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.closes import reconciliations as rec
from abacus.modules.closes import service as closes_service
from abacus.modules.identity.api import Forbidden
from abacus.modules.ledger.month_ledger import MonthAccount, record_month_snapshot
from abacus.modules.ledger.normalise import LedgerLine, NormalisedTrialBalance

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t14_close_record import (
    _Firm,  # pyright: ignore[reportPrivateUsage] -- the close suite's firm builder
)

pytestmark = pytest.mark.asyncio
D = Decimal
CASH = "35"

ACCOUNTS = (
    MonthAccount(
        CASH, "1000", "Operating Checking", "asset", "Bank", None, None, "••4410", False, True
    ),
    MonthAccount("90", "3000", "Owner equity", "equity", "Equity", None, None, None, False, True),
    MonthAccount("68", "6800", "Bank fees", "expense", "Expense", None, None, None, False, True),
)


def _tb(cash: str) -> NormalisedTrialBalance:
    lines = (
        LedgerLine(CASH, "Operating Checking", D(cash), D(0), CASH),
        LedgerLine("90", "Owner equity", D(0), D(cash), "90"),
    )
    return NormalisedTrialBalance(
        date(2026, 8, 1), date(2026, 8, 31), "USD", lines, D(cash), D(cash)
    )


async def _month(firm: _Firm, entity: uuid.UUID, cash: str) -> None:
    system = TenantContext(firm.tenant, "system", "connections:ledger_sync")
    async with uow(system) as tx:
        await record_month_snapshot(
            tx,
            client_entity_id=entity,
            period="2026-08",
            tb=_tb(cash),
            accounts=ACCOUNTS,
            register=[],
            pulled_at=datetime.now(UTC),
            source="quickbooks_online:2026-08",
        )


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


async def _august(firm: _Firm) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    engagement, _, entity = await firm.engagement("Copperleaf Coffee Roasters, Inc.")
    august = (await closes_service.generate_closes(firm.ctx(), engagement, 2026))[7]
    return engagement, entity, august


async def _statement(firm: _Firm, reconciliation: uuid.UUID, bank: str) -> list[uuid.UUID]:
    """What the run step's `close_reconcile_statement` records from a statement: the bank balance
    and two outstanding items, an outstanding check and a deposit in transit."""
    await firm.seed.run(
        "UPDATE reconciliations SET balance_per_bank = $2 WHERE id = $1", reconciliation, D(bank)
    )
    items: list[uuid.UUID] = []
    for kind, side, ref, amount, on in (
        ("outstanding_check", "bank", "Check 1042", D("-400.00"), date(2026, 8, 29)),
        ("deposit_in_transit", "bank", "Deposit 8/31", D("250.00"), date(2026, 8, 31)),
    ):
        items.append(
            cast(
                uuid.UUID,
                await firm.seed.value(
                    "INSERT INTO reconciling_items (tenant_id, reconciliation_id, side, kind, "
                    "ref, txn_date, days_at_period_end, amount, stale) VALUES ($1, $2, $3, $4, "
                    "$5, $6, $7, $8, false) RETURNING id",
                    firm.tenant,
                    reconciliation,
                    side,
                    kind,
                    ref,
                    on,
                    (date(2026, 8, 31) - on).days,
                    amount,
                ),
            )
        )
    return items


async def test_cv2_a_reconciliation_versions_carries_and_resolves(firm: _Firm) -> None:
    engagement, entity, august = await _august(firm)
    await _month(firm, entity, "10000.00")
    tenant = TenantContext(firm.tenant, "system", "closes:reconciliation")

    first = await rec.recompute(tenant, august, CASH)
    assert first is not None
    rows = await firm.seed.rows(
        "SELECT version, tally, book_balance, balance_per_bank FROM reconciliations WHERE id = $1",
        first,
    )
    assert [
        (r["version"], r["tally"], r["book_balance"], r["balance_per_bank"]) for r in rows
    ] == [
        (1, "pending", D("10000.00"), None),
    ]
    assert await rec.recompute(tenant, august, CASH) is None  # the same inputs: no version

    check, deposit = await _statement(firm, first, "10150.00")
    # Bank 10,150.00 - check 400.00 + deposit 250.00 = 10,000.00 adjusted, the book's balance.
    second = await rec.recompute(tenant, august, CASH)
    assert second is not None
    got = (
        await firm.seed.rows(
            "SELECT version, tally, adjusted_bank, adjusted_book, difference FROM reconciliations "
            "WHERE id = $1",
            second,
        )
    )[0]
    assert (got["version"], got["adjusted_bank"], got["adjusted_book"], got["difference"]) == (
        2,
        D("10000.00"),
        D("10000.00"),
        D("0.00"),
    )
    carried = await firm.seed.rows(
        "SELECT id, kind, carried_from_item_id FROM reconciling_items "
        "WHERE reconciliation_id = $1 ORDER BY txn_date",
        second,
    )
    assert [(r["kind"], r["carried_from_item_id"]) for r in carried] == [
        ("outstanding_check", check),
        ("deposit_in_transit", deposit),
    ]
    new_check, new_deposit = (cast(uuid.UUID, r["id"]) for r in carried)

    ctx = firm.ctx()
    view = await rec.view(ctx, august, CASH)
    assert view["account_name"] == "Operating Checking"
    assert view["open_count"] == 2 and view["period_end"] == date(2026, 8, 31)
    facts = await rec.reconciliation_facts(ctx.tenant, second)
    assert facts is not None
    assert (facts.blocked_code, facts.blocked_count, facts.version_no) == (  # type: ignore[attr-defined] -- the facts object
        "reconciling_items_open",
        2,
        2,
    )

    cleared = await rec.resolve_item(ctx, second, new_deposit, "cleared", "  Cleared 9/2  ")
    assert cleared["resolution"] == "cleared"
    with pytest.raises(rec.ItemResolved):
        await rec.resolve_item(ctx, second, new_deposit, "carry_forward", "again")
    await rec.resolve_item(ctx, second, new_check, "carry_forward", "Not yet presented")
    note = await firm.seed.value(
        "SELECT note FROM reconciling_item_resolutions WHERE item_id = $1", new_deposit
    )
    assert note == "Cleared 9/2"
    facts = await rec.reconciliation_facts(ctx.tenant, second)
    assert facts is not None and facts.blocked_code is None  # type: ignore[attr-defined] -- the facts object

    # A ledger sync with a changed book balance recomputes: version 3 carries only the item left
    # to carry, never the cleared one.
    await _month(firm, entity, "9950.00")
    await rec.on_ledger_snapshot_recorded(
        OutboxEvent(
            event_id=uuid.uuid4(),
            tenant_id=firm.tenant,
            event_type="ledger_snapshot.recorded",
            payload={"client_entity_id": str(entity)},
        )
    )
    third = await firm.seed.rows(
        "SELECT id, version, book_balance FROM reconciliations WHERE close_id = $1 "
        "AND account_external_id = $2 ORDER BY version",
        august,
        CASH,
    )
    assert [(r["version"], r["book_balance"]) for r in third] == [
        (1, D("10000.00")),
        (2, D("10000.00")),
        (3, D("9950.00")),
    ]
    left = await firm.seed.rows(
        "SELECT kind, carried_from_item_id FROM reconciling_items WHERE reconciliation_id = $1",
        third[-1]["id"],
    )
    assert [(r["kind"], r["carried_from_item_id"]) for r in left] == [
        ("outstanding_check", new_check)
    ]
    reviewables = await rec.reconciliation_reviewables(ctx.tenant, engagement)
    assert [r.target_id for r in reviewables] == [third[-1]["id"]]  # type: ignore[attr-defined] -- the facts object


async def test_cv2_a_bank_error_item_proposes_its_aje(firm: _Firm) -> None:
    _, entity, august = await _august(firm)
    await _month(firm, entity, "10000.00")
    tenant = TenantContext(firm.tenant, "system", "closes:reconciliation")
    first = await rec.recompute(tenant, august, CASH)
    assert first is not None
    fee = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO reconciling_items (tenant_id, reconciliation_id, side, kind, ref, "
            "txn_date, days_at_period_end, amount, stale) VALUES ($1, $2, 'book', "
            "'unrecorded_withdrawal', 'Service charge', '2026-08-31', 0, -35.00, false) "
            "RETURNING id",
            firm.tenant,
            first,
        ),
    )
    ctx = firm.ctx()
    item = await rec.item_for_draft(ctx, first, fee)
    lines = rec.entry_lines(item, CASH, "68")
    assert lines == [("68", D("35.00"), D(0)), (CASH, D(0), D("35.00"))]
    entry_id, ref = await rec.propose_from_item(ctx, august, fee, " August service charge ", lines)
    assert ref.startswith("AJE-")
    linked = await firm.seed.value(
        "SELECT proposed_entry_id FROM reconciling_items WHERE id = $1", fee
    )
    assert linked == entry_id
    assert rec.entry_lines({"kind": "unrecorded_deposit", "amount": "12.50"}, CASH, "40") == [
        (CASH, D("12.50"), D(0)),
        ("40", D(0), D("12.50")),
    ]
    assert rec.entry_lines({"kind": "book_error", "amount": "9.00"}, CASH, "40")[0][0] == CASH


async def test_cv2_only_a_person_resolves_and_an_unknown_item_is_absent(firm: _Firm) -> None:
    _, entity, august = await _august(firm)
    await _month(firm, entity, "10000.00")
    tenant = TenantContext(firm.tenant, "system", "closes:reconciliation")
    first = await rec.recompute(tenant, august, CASH)
    assert first is not None
    check, _ = await _statement(firm, first, "10150.00")
    with pytest.raises(Forbidden):
        await rec.resolve_item(firm.ctx(actor_kind="agent"), first, check, "cleared", "x")
    with pytest.raises(Forbidden):
        await rec.propose_from_item(firm.ctx(actor_kind="agent"), august, check, "x", [])
    from abacus.kernel.errors import NotFound

    with pytest.raises(NotFound):
        await rec.resolve_item(firm.ctx(), first, uuid.uuid4(), "cleared", "x")
    with pytest.raises(NotFound):
        await rec.item_for_draft(firm.ctx(), first, uuid.uuid4())
    with pytest.raises(NotFound):
        await rec.view(firm.ctx(), august, "no-such-account")
    with pytest.raises(NotFound):
        await rec.recompute(tenant, august, "no-such-account")
    assert await rec.reconciliation_facts(firm.ctx().tenant, uuid.uuid4()) is None
