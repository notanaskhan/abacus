"""C-01-T21 (TASK-8302; C-01 §3 F6; CLS-04) against Postgres: accounts and schedules.

Row acceptance: "Prepaid Insurance shows GL 3,500.00 against schedule 2,800.00 as 'Ties once
posted' while AJE-02 is pending, and after a sync containing the matching JE it reads 'Recorded
in QuickBooks · JE 48214' and ties."
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.adjustments.api import NewEntry, NewLine, propose_entry
from abacus.modules.closes import accounts
from abacus.modules.closes import service as closes_service
from abacus.modules.closes.contract_work import ArrangementIn
from abacus.modules.ledger.month_ledger import (
    MonthAccount,
    MonthRegisterLine,
    record_month_snapshot,
)
from abacus.modules.ledger.normalise import LedgerLine, NormalisedTrialBalance

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase
from .test_c01t14_close_record import (
    _Firm,  # pyright: ignore[reportPrivateUsage] -- the rule under test
)

pytestmark = pytest.mark.asyncio
D = Decimal


def _account(code: str, number: str, name: str, kind: str, kind_type: str) -> MonthAccount:
    mask = "••4410" if code == "35" else None
    return MonthAccount(code, number, name, kind, kind_type, None, None, mask, False, True)


ACCOUNTS = (
    _account("35", "1000", "Operating Checking", "asset", "Bank"),
    _account("41", "1400", "Prepaid Insurance", "asset", "Other Current Asset"),
    _account("90", "3000", "Owner equity", "equity", "Equity"),
    _account("66", "6400", "Insurance", "expense", "Expense"),
)


def _tb(prepaid: str, insurance: str) -> NormalisedTrialBalance:
    lines = (
        LedgerLine("35", "Operating Checking", D("10000.00"), D(0), "35"),
        LedgerLine("41", "Prepaid Insurance", D(prepaid), D(0), "41"),
        LedgerLine("90", "Owner equity", D(0), D("18400.00"), "90"),
        LedgerLine("66", "Insurance", D(insurance), D(0), "66"),
    )
    debit = D("10000.00") + D(prepaid) + D(insurance)
    return NormalisedTrialBalance(date(2026, 8, 1), date(2026, 8, 31), "USD", lines, debit, debit)


def _je() -> list[MonthRegisterLine]:
    """JE 48214: Dr Insurance 700 / Cr Prepaid Insurance 700, as QuickBooks lists it."""
    on, memo, je = date(2026, 8, 31), "August amortization", "Journal Entry"  # dated in month
    return [
        MonthRegisterLine("je1", "66", "48214", on, je, "AJE-02", None, memo, "41", D(700)),
        MonthRegisterLine("je2", "41", "48214", on, je, "AJE-02", None, memo, "66", D(-700)),
    ]


async def _month(
    firm: _Firm, entity: uuid.UUID, tb: NormalisedTrialBalance, register: list[MonthRegisterLine]
) -> None:
    system = TenantContext(firm.tenant, "system", "connections:ledger_sync")
    async with uow(system) as tx:
        await record_month_snapshot(
            tx,
            client_entity_id=entity,
            period="2026-08",
            tb=tb,
            accounts=ACCOUNTS,
            register=register,
            pulled_at=datetime.now(UTC),
            source="quickbooks_online:2026-08",
        )


@pytest.fixture
async def firm(migrated_db: MigratedDatabase) -> AsyncIterator[_Firm]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield await _Firm(Seeder(migrated_db.superuser_dsn)).make()
    await dispose_engine()


async def test_ac_ties_once_posted_then_recorded_in_quickbooks(firm: _Firm) -> None:
    engagement, _, entity = await firm.engagement("Brightwater Hale Cafe")
    august = (await closes_service.generate_closes(firm.ctx(), engagement, 2026))[7]
    await _month(firm, entity, _tb("3500.00", "4900.00"), [])
    policy = await accounts.create_arrangement(
        firm.ctx(),
        august,
        "41",
        ArrangementIn(
            kind="prepaid",
            description="General liability policy",
            expense_account_ref="66",
            scheduled_total=D("8400.00"),
            start_on=date(2026, 1, 1),
            finish_on=date(2026, 12, 31),
        ),
    )
    assert policy.version == 1
    entry = await propose_entry(
        firm.ctx(),
        august,
        NewEntry(
            kind="aje",
            description="August amortization",
            misstatement_id=None,
            lines=(NewLine("66", D("700.00"), D(0)), NewLine("41", D(0), D("700.00"))),
        ),
    )
    paper = await accounts.workpaper(firm.ctx(), august, "41")
    assert (paper.gl_balance, paper.schedule_balance) == (D("3500.00"), D("2800.00"))
    assert paper.tally == "ties_once_posted"
    assert paper.pending_entry_number == entry.ref
    assert paper.off_by == D("700.00")
    # C-02-T56 (CLS-04 a): the pending entry's id; not posted, and not postable until approved.
    assert (paper.pending_entry_id, paper.posting_open, paper.posted_external_ref) == (
        entry.id,
        False,
        None,
    )
    tree = await accounts.account_tree(firm.ctx(), august)
    leaves = [leaf for c in tree.nodes for t in c.children for leaf in t.children]
    assert next(n for n in leaves if n.account_external_id == "41").tally == "ties_once_posted"
    assert sum(c.balance for c in tree.nodes if c.classification == "asset") == D("13500.00")

    # The entry is approved and recorded in QuickBooks; the next sync carries JE 48214.
    await firm.seed.run("UPDATE proposed_entries SET status = 'approved' WHERE id = $1", entry.id)
    approved = await accounts.workpaper(firm.ctx(), august, "41")
    assert (approved.pending_entry_status, approved.posting_open) == ("approved", True)  # CLS-04 b
    await firm.seed.run(
        "UPDATE proposed_entries SET is_attest_client = true WHERE id = $1", entry.id
    )
    attest = await accounts.workpaper(firm.ctx(), august, "41")
    assert attest.posting_open is False  # C-01 DV-1: an attest client stays read-only
    await firm.seed.run(
        "UPDATE proposed_entries SET is_attest_client = false WHERE id = $1", entry.id
    )
    await _month(firm, entity, _tb("2800.00", "5600.00"), _je())
    assert await accounts.match_recordings(firm.ctx(), august) == [entry.id]
    assert await accounts.match_recordings(firm.ctx(), august) == []  # found once
    paper = await accounts.workpaper(firm.ctx(), august, "41")
    assert paper.tally == "recorded"
    assert paper.gl_balance == paper.schedule_balance == D("2800.00")
    assert paper.recording is not None and paper.recording.external_txn_id == "48214"
    kept = await firm.seed.rows(
        "SELECT tie FROM close_schedule_results WHERE close_id = $1 ORDER BY computed_at",
        august,
    )
    assert [r["tie"] for r in kept] == ["ties_once_posted", "recorded"]


async def test_an_edit_is_a_new_version_and_a_stale_edit_is_refused(firm: _Firm) -> None:
    engagement, _, entity = await firm.engagement("Brightwater Hale Cafe")
    august = (await closes_service.generate_closes(firm.ctx(), engagement, 2026))[7]
    await _month(firm, entity, _tb("3500.00", "4900.00"), [])
    body = ArrangementIn(
        kind="prepaid",
        description="Policy",
        expense_account_ref="66",
        scheduled_total=D("8400.00"),
        start_on=date(2026, 1, 1),
        finish_on=date(2026, 12, 31),
    )
    made = await accounts.create_arrangement(firm.ctx(), august, "41", body)
    edited = await accounts.update_arrangement(
        firm.ctx(), made.arrangement_id, body.model_copy(update={"description": "Policy v2"}), "1"
    )
    assert edited.version == 2 and edited.description == "Policy v2"
    with pytest.raises(accounts.ArrangementStale):
        await accounts.update_arrangement(firm.ctx(), made.arrangement_id, body, "1")
    count = await firm.seed.value(
        "SELECT count(*) FROM arrangement_versions WHERE arrangement_id = $1", made.arrangement_id
    )
    assert count == 2


async def test_an_agent_never_edits_an_arrangement(firm: _Firm) -> None:
    engagement, _, entity = await firm.engagement("Brightwater Hale Cafe")
    august = (await closes_service.generate_closes(firm.ctx(), engagement, 2026))[7]
    await _month(firm, entity, _tb("3500.00", "4900.00"), [])
    from abacus.modules.identity.api import Forbidden

    with pytest.raises(Forbidden):
        await accounts.create_arrangement(
            firm.ctx(actor_kind="agent"),
            august,
            "41",
            ArrangementIn(
                kind="prepaid",
                description="Policy",
                expense_account_ref="66",
                scheduled_total=D("8400.00"),
                start_on=date(2026, 1, 1),
                finish_on=date(2026, 12, 31),
            ),
        )
