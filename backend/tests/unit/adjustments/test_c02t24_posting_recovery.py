"""C-02-T24 (TASK-8809; SPEC-700 F3 US-3.2 to US-3.5): posting failures and conflicts.

Row acceptance: "AJE-03 fails on the inactive account, posts on Retry without a duplicate, and an
Aug 31 entry against an Aug 31 closing date offers only ask-client or re-date." Here, at the
writer and module seams (the DB-backed walk is the end pass's): an inactive account fails without
a write and the same idempotency key posts once after reactivation; a closing-date failure opens a
conflict instead of an issue; the conflict's only routes are ask-client and re-date; a retry
payload names one entry; the CLS-07e line reads from codes.
"""

from __future__ import annotations

import ast
from datetime import date
from decimal import Decimal
from pathlib import Path

from abacus.modules.adjustments import posting_recovery
from abacus.modules.adjustments.posting_types import PostingInput
from abacus.modules.closes.registrations import _next_period  # pyright: ignore[reportPrivateUsage]
from abacus.modules.integrations.api import (
    FakeQboTransport,
    JournalEntry,
    JournalLine,
    QuickBooksOnlineWriter,
)

SRC = Path(posting_recovery.__file__).parent
AJE_03 = JournalEntry(
    "AJE-03",
    date(2026, 8, 31),
    (
        JournalLine("1090", "Debit", Decimal("1150.00")),
        JournalLine("1595", "Credit", Decimal("1150.00")),
    ),
)


async def test_ac_inactive_account_fails_then_posts_once_on_retry() -> None:
    fake = FakeQboTransport(accounts={"1090": True, "1595": False})
    writer = QuickBooksOnlineWriter(fake)
    first = await writer.post(AJE_03, "batch:aje-03")
    assert first.error == "inactive_account" and fake.writes == []
    fake.accounts["1595"] = True  # reactivated in QuickBooks
    second = await writer.post(AJE_03, "batch:aje-03")
    again = await writer.post(AJE_03, "batch:aje-03")  # a replayed retry: the same answer
    assert second.verified and again.external_ref == second.external_ref
    assert [w for w in fake.writes if w[0] == "POST JournalEntry"] == [("POST JournalEntry", "AJE-03")]


async def test_ac_closing_date_failure_is_a_conflict_not_an_issue() -> None:
    fake = FakeQboTransport(accounts={"1090": True, "1595": True}, closed_on=date(2026, 8, 31))
    posted = await QuickBooksOnlineWriter(fake).post(AJE_03, "batch:aje-03")
    assert posted.error == "closing_date_locked" and fake.writes == []

    class _Tx:
        def __init__(self) -> None:
            self.recorded: list[str] = []

            class _S:
                async def scalar(self, *_: object, **__: object) -> object:
                    return "c-1"

            self.session = _S()

        def record(self, action: str, **_: object) -> None:
            self.recorded.append(action)

    tx = _Tx()
    is_issue = await posting_recovery.record_failure(
        tx, tenant_id=__import__("uuid").uuid4(), batch_id=__import__("uuid").uuid4(),
        entry_id=__import__("uuid").uuid4(), entry_date=date(2026, 8, 31),
        code="closing_date_locked", closed_on=date(2026, 8, 31),
    )  # fmt: skip
    assert is_issue is False and tx.recorded == ["closing_date_conflict.opened"]


def test_ac_a_conflict_offers_only_ask_client_or_redate() -> None:
    tree = ast.parse((SRC / "posting_contract.py").read_text(encoding="utf-8"))
    routes = [
        ast.literal_eval(d.args[0])
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncFunctionDef)
        for d in n.decorator_list
        if isinstance(d, ast.Call) and d.args and isinstance(d.args[0], ast.Constant)
    ]
    conflict = sorted(r for r in routes if r.startswith("/closing-date-conflicts/"))
    assert conflict == [
        "/closing-date-conflicts/{conflict_id}/ask-client",
        "/closing-date-conflicts/{conflict_id}/redate",
    ]


def test_a_retry_names_one_entry_and_its_grant_and_old_payloads_still_read() -> None:
    old = PostingInput("t", "b")
    assert old.entry_id is None and old.grant_id is None
    assert PostingInput("t", "b", "e", "g").entry_id == "e"


def test_the_cls07e_line_reads_from_codes() -> None:
    facts = posting_recovery.FailedEntryFacts(
        __import__("uuid").uuid4(), "AJE-03", "inactive_account", "Accumulated Depreciation", 1
    )
    assert posting_recovery.failure_line(facts) == (
        "QuickBooks Online: account 'Accumulated Depreciation' is inactive"
    )


def test_reversals_carry_into_the_next_period() -> None:
    assert _next_period("2026-08") == "2026-09"
    assert _next_period("2026-12") == "2027-01"
