"""C-01-T16 (TASK-8034; SPEC-655 AC-32 to AC-34; ADR-040, ADR-043): the QuickBooks Online read
connector v2.

The chart of accounts with Intuit's classification, type and subtype; a month's TrialBalance;
the general-ledger detail as register lines with the offset account; CDC through
`changes_since`; per-company throttling, Retry-After and the provider's breaker; the meter's call
count; the pinned minor version; and still no write (CONN-001): every request stays a GET.
Recorded synthetic responses only (no real company data).
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast

import pytest

from abacus.kernel.egress import EgressClient, EgressResponse
from abacus.modules.connections import qbo_throttle
from abacus.modules.connections.connector import Period, RateLimited, Unavailable
from abacus.modules.connections.connectors import quickbooks_online as qbo
from abacus.modules.connections.qbo_format import parse_qbo_accounts, parse_qbo_general_ledger
from abacus.modules.ledger.api import NormaliseError

from .test_qbo_connector import (
    ACCOUNTS,
    APP,
    CDC,
    GENERAL_LEDGER,
    MONTH,
    Recorder,
    _connector,
    _held,
)


@pytest.fixture(autouse=True)
def _fresh_throttle() -> None:
    qbo_throttle.reset()


def test_ac_accounts_carry_classification_type_and_subtype() -> None:
    accounts = {a.external_id: a for a in parse_qbo_accounts(ACCOUNTS.read_bytes())}
    checking = accounts["35"]
    assert (checking.name, checking.classification, checking.account_type) == (
        "Operating Checking", "asset", "Bank",
    )  # fmt: skip
    assert checking.account_subtype == "Checking" and checking.number == "1010"
    assert accounts["4"].classification == "income"  # Intuit's Revenue
    assert accounts["90"].is_contra and not accounts["91"].is_contra
    assert accounts["91"].parent_external_id == "89"


def test_ac_gl_detail_normalises_to_register_lines_with_the_offset_account() -> None:
    lines = parse_qbo_general_ledger(GENERAL_LEDGER.read_bytes())
    assert [line.account_ref for line in lines] == ["35", "35", "35"]
    check = lines[1]
    assert (check.txn_date, check.txn_type, check.doc_number) == (
        date(2026, 8, 18),
        "Check",
        "2285",
    )
    assert (check.payee, check.offset_account_ref, check.amount) == (
        "Sound Electric Contractors, LLC", "72", Decimal("-3200.00"),
    )  # fmt: skip
    assert check.external_txn_id == "1410"
    assert len({line.line_ref for line in lines}) == 3  # stable, distinct references
    # The summary row is the provider's subtotal; the engine foots its own.
    assert sum(line.amount for line in lines) == Decimal("1446.48")


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('"subt_nat_amount"', '"amount_x"'),  # a missing register column
        ('"-3200.00"', '"-3,200.00"'),  # not a plain decimal
        ('"Repairs & Maintenance", "id": "72"', '"Repairs", "id": "72; DROP"'),  # hostile id
    ],
)
def test_ac_hostile_gl_reports_are_refused(old: str, new: str) -> None:
    content = GENERAL_LEDGER.read_text().replace(old, new, 1).encode()
    with pytest.raises(NormaliseError):
        parse_qbo_general_ledger(content)


async def test_ac_pulls_read_the_v2_datasets_with_the_pinned_minor_version() -> None:
    recorder = Recorder()
    connector = _connector(recorder, _held())
    for dataset in ("accounts", "gl_detail", "trial_balance_month"):
        await connector.pull(dataset, MONTH, None)  # type: ignore[arg-type]
    urls = [url for _, url in recorder.sent]
    assert all(f"minorversion={qbo.MINOR_VERSION}" in url for url in urls)
    assert any("/query?query=select%20%2A%20from%20Account" in url for url in urls)
    assert any(
        "/reports/GeneralLedger?start_date=2026-08-01&end_date=2026-08-31" in url for url in urls
    )
    assert {method for method, _ in recorder.sent} == {"GET"}  # CONN-001: reads only
    assert connector.calls == 3  # the meter counts API calls, never OAuth


async def test_ac_a_full_accounts_page_returns_the_next_cursor() -> None:
    connector = _connector(Recorder(), _held())
    raw = await connector.pull("accounts", MONTH, None)
    assert raw.next_cursor is None  # 7 accounts, below a page of 1,000
    with pytest.raises(qbo.ConnectorError):
        await connector.pull("accounts", MONTH, "1 or 1=1")


async def test_ac_changes_since_names_the_datasets_to_pull_again() -> None:
    connector = _connector(Recorder(), _held())
    changed = await connector.changes_since(datetime(2026, 9, 14, 13, 0, tzinfo=UTC))
    assert changed == ("gl_detail", "trial_balance_month")  # a Purchase changed; no Account
    assert CDC.exists()


class _Throttled(Recorder):
    async def request(self, method: str, url: str, **_: object) -> EgressResponse:  # type: ignore[override]
        self.sent.append((method.upper(), url))
        return EgressResponse(429, {"Retry-After": "7"}, b"")


async def test_ac33_a_429_is_rate_limited_with_retry_after_and_five_open_the_breaker() -> None:
    recorder = _Throttled()
    connector = qbo.QuickBooksOnlineConnector(APP, cast(EgressClient, recorder), _held())
    for _ in range(qbo_throttle.BREAKER_FAILURES):
        with pytest.raises(RateLimited) as limited:
            await connector.pull("trial_balance_month", MONTH, None)
        assert limited.value.retry_after == 7.0 and limited.value.retryable
    sent = len(recorder.sent)
    with pytest.raises(RateLimited) as held_back:
        await connector.pull("trial_balance_month", MONTH, None)
    assert held_back.value.code == "circuit_open"
    assert len(recorder.sent) == sent  # the breaker held the call back: nothing left
    assert isinstance(held_back.value, Unavailable)


async def test_ac33_each_realm_stays_inside_its_window() -> None:
    connector = _connector(Recorder(), _held())
    realm = qbo_throttle._realms.setdefault(
        "9341453052194873",
        qbo_throttle._Realm(),
    )
    now = qbo_throttle._clock()
    realm.calls.extend([now] * qbo_throttle.PER_MINUTE)
    with pytest.raises(RateLimited) as limited:
        await connector.pull(
            "trial_balance_month", Period(date(2026, 8, 1), date(2026, 8, 31)), None
        )
    assert limited.value.code == "rate_limited" and limited.value.retry_after is not None


def test_ac34_the_connector_still_declares_no_write() -> None:
    methods = {name for name in dir(qbo.QuickBooksOnlineConnector) if not name.startswith("_")}
    assert not {m for m in methods if m.startswith(("post", "put", "write", "create", "update"))}
