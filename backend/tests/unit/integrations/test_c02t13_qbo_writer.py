"""C-02-T13 (SPEC-700; DEC-5623): the QBO W1 writer against the fake. An AJE posts once under a
repeated request, the read-back matches line for line, an inactive account fails preflight with
no write, and the interception record shows no other non-GET call."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from abacus.modules.integrations.writers.quickbooks_online import (
    FakeQboTransport,
    JournalEntry,
    JournalLine,
    QuickBooksOnlineWriter,
)

D = Decimal


def _aje(debit_ref: str = "61", credit_ref: str = "33") -> JournalEntry:
    return JournalEntry(
        "AJE-01",
        date(2026, 8, 31),
        (
            JournalLine(debit_ref, "Debit", D("4200.00"), "Payroll accrual"),
            JournalLine(credit_ref, "Credit", D("4200.00"), "Accrued payroll"),
        ),
    )


async def test_posts_once_under_a_repeated_request_and_reads_back() -> None:
    fake = FakeQboTransport(accounts={"61": True, "33": True}, closed_on=date(2026, 7, 31))
    writer = QuickBooksOnlineWriter(fake)
    first = await writer.post(_aje(), "req-aje-01")
    again = await writer.post(_aje(), "req-aje-01")
    assert first.external_ref == again.external_ref == "48213"
    assert first.verified and again.verified
    assert fake.writes == [("POST JournalEntry", "AJE-01")]


async def test_inactive_account_fails_preflight_without_a_write() -> None:
    fake = FakeQboTransport(accounts={"61": True, "33": False})
    writer = QuickBooksOnlineWriter(fake)
    check = await writer.preflight(_aje())
    assert (check.ok, check.failed_check, check.account_ref) == (False, "inactive_account", "33")
    posted = await writer.post(_aje(), "req-aje-03")
    assert posted.error == "inactive_account"
    assert fake.writes == []


async def test_closed_period_unbalanced_and_unmapped_are_refused() -> None:
    fake = FakeQboTransport(accounts={"61": True, "33": True}, closed_on=date(2026, 8, 31))
    writer = QuickBooksOnlineWriter(fake)
    assert (await writer.preflight(_aje())).failed_check == "closed_period"
    lopsided = JournalEntry("AJE-02", date(2026, 9, 1), (JournalLine("61", "Debit", D("1")),))
    assert (await writer.preflight(lopsided)).failed_check == "unbalanced"
    unmapped = _aje(debit_ref="61", credit_ref="33")
    unmapped = JournalEntry(
        "AJE-04", date(2026, 9, 1), (unmapped.lines[0], JournalLine(None, "Credit", D("4200.00")))
    )
    assert (await writer.preflight(unmapped)).failed_check == "unmapped_account"
    assert fake.writes == []


async def test_provider_errors_map_to_codes() -> None:
    fake = FakeQboTransport(
        accounts={"61": True, "33": True}, script=["rate_limited", "needs_reauth"]
    )
    writer = QuickBooksOnlineWriter(fake)
    assert (await writer.post(_aje(), "r1")).error == "rate_limited"
    assert (await writer.post(_aje(), "r2")).error == "needs_reauth"
    assert fake.writes == []


async def test_book_close_date_is_the_only_other_write() -> None:
    fake = FakeQboTransport(accounts={"61": True, "33": True})
    writer = QuickBooksOnlineWriter(fake)
    await writer.post(_aje(), "r1")
    assert await writer.set_book_close_date(date(2026, 8, 31), "close-2026-08") is None
    assert [w[0] for w in fake.writes] == ["POST JournalEntry", "POST Preferences.BookCloseDate"]
