# ac-test-author: ayushkbhatia
"""Q-03-T024: back-fill of TASK-068 (SPEC-028 AC-2 to AC-6 and AC-8 for QuickBooks Desktop,
NetSuite and Sage Intacct, beside QuickBooks Online and Xero): each of the five trial balance
formats round-trips, quirks are read correctly, a failed check snapshots nothing, the same file is
recognised, and the fulfilment of the trial balance item never marks it received without a human
decision.

"Received" is DEC-09's code: the repo's old `received` became `uploaded` ("Uploaded - needs
review"), and `received` now means a person accepted the evidence. An import fulfils as
`uploaded`.

Boundary: `create_app()` over HTTP as the engagement partner (SPEC-028 Q4, on the client's
behalf), the compose S3 image, the local scanner, and the real worker pools on a Temporal dev
server (SPEC-028 §6 step 4: the import becomes the entity's import connection and the retrieval
of the open tier A trial balance item runs the pipeline). Every figure is typed from the literal
trial balance in `ledger_support.py`.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Callable, Iterator
from contextlib import AsyncExitStack, asynccontextmanager
from decimal import Decimal
from typing import Final

import pytest
from temporalio.client import Client
from temporalio.worker import Worker
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.scanning import forget_injected
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.kernel.uow.relay import run_relay
from abacus.worker.__main__ import build_workers, publisher
from abacus_tools.synthetic.ledger_exports import (
    intacct_trial_balance_csv,
    netsuite_trial_balance_csv,
    qbd_trial_balance_xlsx,
    qbo_trial_balance_csv,
    xero_trial_balance_xlsx,
)
from abacus_tools.synthetic.model import TrialBalance

from .ledger_support import EXPECTED, TB, TOTAL, Ledger, bucket, ledger, wire_storage
from .support import Net

BUCKET: Final = f"backfill-tb-{uuid.uuid4().hex[:10]}"
MASTER: Final = b"backfill-tb-formats-master-key-0123456789"
QUEUE: Final = f"backfill-tb-{uuid.uuid4().hex[:10]}"
WRITERS: Final[dict[str, Callable[[TrialBalance], bytes]]] = {
    "QuickBooks Online": qbo_trial_balance_csv,
    "Xero": xero_trial_balance_xlsx,
    "QuickBooks Desktop": qbd_trial_balance_xlsx,
    "NetSuite": netsuite_trial_balance_csv,
    "Sage Intacct": intacct_trial_balance_csv,
}


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> S3Client:
    return bucket(s3_settings, BUCKET)


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    forget_injected()
    yield from wire_storage(raw, BUCKET, MASTER)
    forget_injected()


@pytest.fixture(autouse=True)
def task_queue(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", QUEUE)
    settings.cache_clear()
    yield
    settings.cache_clear()
    configure_temporal_client(None)


@asynccontextmanager
async def _serving() -> AsyncGenerator[list[Worker]]:
    """Every class's pool and the outbox relay, as `python -m abacus.worker` runs them."""
    stop = asyncio.Event()
    async with AsyncExitStack() as pools:
        built = await build_workers()
        for pool in built:
            await pools.enter_async_context(pool)
        relay = asyncio.create_task(run_relay(publisher(), stop, interval=0.2))
        try:
            yield built
        finally:
            stop.set()
            await relay


@pytest.fixture
async def worker(temporal_target: str) -> AsyncIterator[list[Worker]]:
    client = await Client.connect(temporal_target, data_converter=data_converter())
    configure_temporal_client(client)
    async with _serving() as built:
        yield built


@pytest.fixture
async def books(net: Net, worker: list[Worker]) -> Ledger:
    return await ledger(net)


async def _lines(books: Ledger) -> dict[str, tuple[Decimal, Decimal]]:
    rows = await books.seed.rows(
        "SELECT l.account_code, l.debit, l.credit FROM trial_balance_lines l "
        "JOIN ledger_snapshots s ON s.id = l.snapshot_id WHERE s.tenant_id = $1",
        books.tenant_id,
    )
    return {str(r["account_code"]): (Decimal(r["debit"]), Decimal(r["credit"])) for r in rows}


async def _imported(books: Ledger, content: bytes, system: str) -> uuid.UUID:
    item = await books.requested("Year-end trial balance")
    response = await books.upload_tb(content, system)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "received", response.text  # the import's own status
    await books.snapshotted()
    return item


# --- AC-2 and AC-4 (TASK-068): each of the five formats round-trips -----------------------------


async def test_ac2_the_formats_route_offers_the_five_systems_with_steps(books: Ledger) -> None:
    response = await books.net.call("GET", f"{books.base}/formats", books.partner)
    assert response.status_code == 200, response.text
    systems = {f["system"]: f for f in response.json()}
    assert set(WRITERS) <= set(systems)
    for system in WRITERS:
        assert systems[system]["steps"], system  # numbered export steps per system
        assert systems[system]["file_type"], system


@pytest.mark.parametrize("system", list(WRITERS))
async def test_ac4_each_of_the_five_formats_round_trips_to_the_same_balances(
    books: Ledger, system: str
) -> None:
    await _imported(books, WRITERS[system](TB), system)
    assert await _lines(books) == EXPECTED
    totals = await books.seed.rows(
        "SELECT total_debit, total_credit FROM ledger_snapshots WHERE tenant_id = $1",
        books.tenant_id,
    )
    assert [(Decimal(r["total_debit"]), Decimal(r["total_credit"])) for r in totals] == [
        (TOTAL, TOTAL)
    ]


@pytest.mark.parametrize("system", list(WRITERS))
async def test_ac4_the_fulfilment_is_imported_and_never_received_without_a_person(
    books: Ledger, system: str
) -> None:
    item = await _imported(books, WRITERS[system](TB), system)
    await books.fulfilled(item)
    rows = await books.seed.rows(
        "SELECT v.method FROM fulfilments f JOIN evidence_versions v "
        "ON v.id = f.evidence_version_id WHERE f.request_item_id = $1",
        item,
    )
    assert [r["method"] for r in rows] == ["imported"]
    assert await books.item_status(item) == "uploaded"


# --- AC-5: signed balances, parentheses, thousands separators, total rows ------------------------


@pytest.mark.parametrize(
    ("system", "content"),
    [
        ("QuickBooks Online", qbo_trial_balance_csv(TB, negative_debits=True)),
        ("QuickBooks Online", qbo_trial_balance_csv(TB, total_row=False, headings=False)),
        ("Xero", xero_trial_balance_xlsx(TB, parentheses=True, total_row=False)),
        ("QuickBooks Desktop", qbd_trial_balance_xlsx(TB, total_row=False)),
        ("NetSuite", netsuite_trial_balance_csv(TB, by_month=False, amount_headers=True)),
        ("Sage Intacct", intacct_trial_balance_csv(TB, parentheses=False)),
    ],
    ids=["qbo-negative-debits", "qbo-no-total", "xero-parens", "qbd-no-total", "ns", "intacct"],
)
async def test_ac5_quirks_are_read_as_the_same_balances(
    books: Ledger, system: str, content: bytes
) -> None:
    await _imported(books, content, system)
    assert await _lines(books) == EXPECTED


# --- AC-6: a failed check is a fixed reason; nothing is snapshotted or fulfilled -----------------


@pytest.mark.parametrize(
    ("system", "written_by"),
    [("NetSuite", "Sage Intacct"), ("QuickBooks Desktop", "Xero"), ("Sage Intacct", "NetSuite")],
)
async def test_ac6_another_systems_file_fails_and_fulfils_nothing(
    books: Ledger, system: str, written_by: str
) -> None:
    item = await books.requested("Year-end trial balance")
    response = await books.upload_tb(WRITERS[written_by](TB), system)
    assert response.status_code in (201, 422), response.text
    if response.status_code == 201:
        assert response.json()["status"] == "failed"
        assert response.json()["failure_code"]
        latest = await books.net.call("GET", books.base, books.manager)
        assert latest.status_code == 200
        assert latest.json()["failure_code"] == response.json()["failure_code"]
    assert await books.count("ledger_snapshots") == 0
    assert await books.item_status(item) == "requested"


# --- AC-8: the same export twice is recognised and makes no second snapshot ---------------------


@pytest.mark.parametrize("system", ["QuickBooks Desktop", "NetSuite", "Sage Intacct"])
async def test_ac8_the_same_export_twice_makes_no_second_snapshot(
    books: Ledger, system: str
) -> None:
    content = WRITERS[system](TB)
    await _imported(books, content, system)
    again = await books.upload_tb(content, system)
    assert again.status_code in (200, 201), again.text
    assert again.json()["duplicate"] is True
    assert await books.count("ledger_snapshots") == 1
