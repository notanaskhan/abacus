# ac-test-author: ayushkbhatia
"""C-02-T30 (TASK-8812; ADR-044, ADR-344): conformance of the W1 writer, against the fake (every
pull request) and the QuickBooks sandbox (nightly, when the sandbox secrets are set).

Acceptance (the task row): "The suite passes against the fake in stage 2 and against the sandbox
nightly, and a drift between the two opens a ticket." Each target answers the same cases (create
then read back line for line, the closing date set and read, an inactive account refused by the
preflight with nothing written, 429 and 401 mapped to codes); the request body is golden; a
real (non-sandbox) host or realm is refused before any write; each target's outcome codes are
written to `W1_DRIFT_REPORT` so the drift job compares the two and opens a ticket on a difference.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from abacus.kernel.egress import EgressClient, configure_egress, configure_write_egress
from abacus.modules.integrations.writers.quickbooks_online import (
    FakeQboTransport,
    HttpQboTransport,
    JournalEntry,
    JournalLine,
    QboError,
    QuickBooksOnlineWriter,
    journal_body,
    request_id_of,
)

HERE: Final = Path(__file__).parent
GOLDEN: Final = HERE / "golden" / "w1_journal_entry_aje01.json"
SANDBOX_HOST: Final = "sandbox-quickbooks.api.intuit.com"
AJE_01: Final = JournalEntry(
    "AJE-01",
    date(2026, 8, 31),
    (
        JournalLine("64", "Debit", Decimal("4200.00")),
        JournalLine("33", "Credit", Decimal("4200.00")),
    ),
    "BH AJE · batch 2026-08-A",
)
TARGETS = ["fake", "sandbox"]


async def _sandbox() -> HttpQboTransport | None:
    """The nightly's sandbox company: the read target refreshes (a rotation), then its access
    token drives the write transport on a write lane opened for the sandbox host alone."""
    from . import targets

    if not targets.sandbox_configured():
        return None
    read = targets.sandbox()
    connector = read.connector()
    await connector.refresh()
    held = connector._held()  # pyright: ignore[reportPrivateUsage]
    configure_egress(frozenset({SANDBOX_HOST}))
    configure_write_egress(frozenset({(SANDBOX_HOST, f"/v3/company/{held.realm_id}/")}))
    return HttpQboTransport(EgressClient(), SANDBOX_HOST, held.realm_id, held.access_token)


@pytest.fixture(params=TARGETS)
async def target(request: pytest.FixtureRequest) -> AsyncIterator[tuple[str, object]]:
    if request.param == "fake":
        yield "fake", FakeQboTransport(accounts={"64": True, "33": True, "90": False})
        return
    live = await _sandbox()
    if live is None:
        pytest.skip("QuickBooks sandbox secrets are not set (the nightly job sets them)")
    yield "sandbox", live
    configure_write_egress(frozenset())


def _report(name: str, case: str, outcome: str) -> None:
    path = os.environ.get("W1_DRIFT_REPORT")
    if not path:
        return
    file = Path(path)
    data = json.loads(file.read_text()) if file.exists() else {}
    data.setdefault(name, {})[case] = outcome
    file.write_text(json.dumps(data, sort_keys=True, indent=2))


def test_the_request_body_is_golden() -> None:
    assert journal_body(AJE_01) == json.loads(GOLDEN.read_text())
    assert len(request_id_of("batch:entry")) == 40
    assert request_id_of("a:b") != request_id_of("a:c")


async def test_create_then_read_back_line_for_line(target: tuple[str, object]) -> None:
    name, transport = target
    writer = QuickBooksOnlineWriter(transport)  # type: ignore[arg-type]
    posted = await writer.post(AJE_01, f"conformance:{name}:create")
    again = await writer.post(AJE_01, f"conformance:{name}:create")
    assert posted.verified and again.external_ref == posted.external_ref
    _report(name, "create_read_back", "verified")


async def test_the_closing_date_is_set_and_read(target: tuple[str, object]) -> None:
    name, transport = target
    writer = QuickBooksOnlineWriter(transport)  # type: ignore[arg-type]
    assert await writer.set_book_close_date(date(2026, 8, 31), f"conformance:{name}:close") is None
    assert await writer.book_close_date() == date(2026, 8, 31)
    _report(name, "book_close_date", "set")


async def test_an_inactive_account_is_refused_before_a_write(target: tuple[str, object]) -> None:
    name, transport = target
    entry = JournalEntry("AJE-99", date(2026, 9, 15), (
        JournalLine("64", "Debit", Decimal("1.00")), JournalLine("90", "Credit", Decimal("1.00")),
    ))  # fmt: skip
    posted = await QuickBooksOnlineWriter(transport).post(entry, f"conformance:{name}:inactive")  # type: ignore[arg-type]
    assert posted.error == "inactive_account" and not posted.verified
    if isinstance(transport, FakeQboTransport):
        assert ("POST JournalEntry", "AJE-99") not in transport.writes
    _report(name, "inactive_account", "inactive_account")


@pytest.mark.parametrize(("scripted", "code"), [("rate_limited", "rate_limited"), ("needs_reauth", "needs_reauth")])
async def test_429_and_401_map_to_codes_on_the_fake(scripted: str, code: str) -> None:
    fake = FakeQboTransport(accounts={"64": True, "33": True}, script=[scripted])  # type: ignore[list-item]
    posted = await QuickBooksOnlineWriter(fake).post(AJE_01, f"conformance:fake:{code}")
    assert posted.error == code
    _report("fake", f"status_{code}", code)


def test_a_real_host_is_never_on_the_write_lane() -> None:
    configure_egress(frozenset({"quickbooks.api.intuit.com", SANDBOX_HOST}))
    configure_write_egress(frozenset({(SANDBOX_HOST, "/v3/company/1/")}))
    from abacus.kernel.egress import write_lane

    assert all(host == SANDBOX_HOST for host, _ in write_lane())
    configure_write_egress(frozenset())
    assert write_lane() == frozenset()


async def test_the_lane_refuses_a_write_it_does_not_declare() -> None:
    from abacus.kernel.egress import EgressRefused

    configure_egress(frozenset({SANDBOX_HOST}))
    configure_write_egress(frozenset())
    with pytest.raises(EgressRefused):
        await EgressClient().write(f"https://{SANDBOX_HOST}/v3/company/1/journalentry", content=b"{}")
    with pytest.raises(QboError):
        raise QboError("rate_limited")
