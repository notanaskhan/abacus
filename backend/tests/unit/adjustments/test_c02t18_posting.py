"""C-02-T18 (TASK-8707; ADR-344; DEC-5704): batch codes, the grant's payload hash, one journal
entry per entry however often a batch is retried (Batch 2026-08-A posts six entries as 48213 to
48218 and sets Aug 31, 2026 once), and the W1 gate: `execute_write` runs the writer only when
every switch is on, and refuses (audited) while the registry keeps W1 dark."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest

from abacus.modules.adjustments import posting
from abacus.modules.integrations import writes
from abacus.modules.integrations.api import (
    FakeQboTransport,
    JournalEntry,
    JournalLine,
    QuickBooksOnlineWriter,
    W1Refused,
    W1Scope,
)

D = Decimal


def _entry(n: int, amount: str = "100.00") -> Any:  # noqa: ANN401 # Any: posting's entry
    return posting._Entry(
        uuid4(),
        f"AJE-{n:02d}",
        "approved",
        1,
        False,
        date(2026, 8, 31),
        (JournalLine("10", "Debit", D(amount)), JournalLine("20", "Credit", D(amount))),
        D(amount),
    )


def test_ac_batch_codes_take_the_next_letter() -> None:
    assert posting.next_code("2026-08", []) == "2026-08-A"
    assert posting.next_code("2026-08", ["2026-08-A", "2026-08-B"]) == "2026-08-C"


def test_ac_the_grant_is_bound_to_entries_lines_and_closing_date() -> None:
    entries = [_entry(1), _entry(2)]
    a = posting.payload_digest("2026-08-A", "2026-08", date(2026, 8, 31), entries)
    assert a == posting.payload_digest("2026-08-A", "2026-08", date(2026, 8, 31), entries)
    assert a != posting.payload_digest("2026-08-A", "2026-08", None, entries)
    assert a != posting.payload_digest("2026-08-A", "2026-08", date(2026, 8, 31), [_entry(1)])


@pytest.mark.asyncio
async def test_ac_six_entries_post_once_as_48213_to_48218_however_often_retried() -> None:
    fake = FakeQboTransport(accounts={"10": True, "20": True})
    writer = QuickBooksOnlineWriter(fake)
    batch = uuid4()
    entries = [_entry(n) for n in range(1, 7)]
    first = [
        await writer.post(JournalEntry(e.ref, e.txn_date, e.lines), f"{batch}:{e.id}")
        for e in entries
    ]
    again = [
        await writer.post(JournalEntry(e.ref, e.txn_date, e.lines), f"{batch}:{e.id}")
        for e in entries
    ]
    assert [p.external_ref for p in first] == [str(n) for n in range(48213, 48219)]
    assert [p.external_ref for p in again] == [p.external_ref for p in first]
    assert all(p.verified for p in first)
    assert sum(1 for w in fake.writes if w[0] == "POST JournalEntry") == 6
    assert await writer.set_book_close_date(date(2026, 8, 31), f"{batch}:closing") is None
    assert fake.closed_on == date(2026, 8, 31)


@asynccontextmanager
async def _no_db(_: object) -> AsyncIterator[Any]:  # Any: a stand-in unit of work
    yield SimpleNamespace(record=lambda *a, **k: None)


def _ctx() -> Any:  # noqa: ANN401 # Any: a stand-in actor (tenant only)
    return SimpleNamespace(tenant=SimpleNamespace(tenant_id=uuid4()), tenant_id=uuid4())


SCOPE = W1Scope(uuid4(), uuid4(), uuid4(), uuid4())


@pytest.mark.asyncio
async def test_ac_the_writer_runs_only_when_every_switch_is_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def all_on(*_: object) -> None:
        return None

    monkeypatch.setattr(writes, "w1_refusal", all_on)
    ran: list[UUID] = []

    async def perform() -> str:
        ran.append(SCOPE.client_id)
        return "48213"

    out = await writes.execute_write(
        _ctx(),
        writes.W1_CAPABILITY,
        SCOPE.client_id,
        approval_ref=uuid4(),
        idempotency_key="batch:entry",
        w1=SCOPE,
        perform=perform,
    )
    assert out == "48213" and ran == [SCOPE.client_id]


@pytest.mark.asyncio
async def test_ac_w1_stays_dark_while_the_registry_keeps_it_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def not_attest(*_: object) -> bool:
        return False

    monkeypatch.setattr(writes, "attest_client_of", not_attest)
    monkeypatch.setattr(writes, "uow", _no_db)
    ran: list[bool] = []

    async def perform() -> None:
        ran.append(True)

    with pytest.raises(W1Refused) as refused:
        await writes.execute_write(
            _ctx(),
            writes.W1_CAPABILITY,
            SCOPE.client_id,
            approval_ref=uuid4(),
            idempotency_key="batch:entry",
            w1=SCOPE,
            perform=perform,
        )
    assert refused.value.facts["reason"] == "write_capability_not_released"
    assert ran == []


@pytest.mark.asyncio
async def test_ac_an_attest_client_is_never_posted_to(monkeypatch: pytest.MonkeyPatch) -> None:
    async def attest(*_: object) -> bool:
        return True

    monkeypatch.setattr(writes, "attest_client_of", attest)
    assert await writes.w1_refusal(_ctx().tenant, SCOPE) == "attest_client_posting_refused"
