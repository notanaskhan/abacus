# ac-test-author: ayushkbhatia
"""Q-03-T023 and Q-03-T024: back-fills of TASK-069 (SPEC-034 AC-2, AC-3, AC-4, AC-5, AC-7,
AC-8: general ledger detail scanned, parsed in isolation, checked against the year-end trial
balance by code, and kept as an immutable snapshot), TASK-070 (AC-6, AC-7: the general ledger and
journal listing workbooks fulfil the open tier A items) and TASK-071 (AC-1 to AC-3 for the three
further systems: all five formats round-trip).

Row acceptance: a GL snapshot is never updated in place (Q-03-T023), each of the five formats has
a round-trip test, and fulfilment never marks a request received without a human decision
(Q-03-T024). "Received" is DEC-09's code: repo `received` became `uploaded` ("Uploaded - needs
review"), and `received` now means a person accepted it; an automatic fulfilment lands as
`uploaded`.

Boundary: `create_app()` over HTTP as the engagement partner (SPEC-028 Q4: on the client's
behalf), the compose S3 image with Object Lock, the local scanner, and the real worker pools
(`build_workers`) on a Temporal dev server so the `GlImport` workflow runs as in production.
Expectations: SPEC-034 §4 and §5, the GL route's documented statuses (`processing`,
`waiting_for_tb`, `reconciled`, `failed`), DEC-09, `error-codes.yaml`. Every figure is typed from
the literal trial balance in `ledger_support.py`.
"""

from __future__ import annotations

import asyncio
import io
import uuid
import zipfile
from collections.abc import AsyncGenerator, AsyncIterator, Iterator
from contextlib import AsyncExitStack, asynccontextmanager
from decimal import Decimal
from typing import Final, cast

import asyncpg
import pytest
from openpyxl import Workbook
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from temporalio.client import Client
from temporalio.worker import Worker
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.scanning import forget_injected, inject_verdict
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.kernel.uow import Target, uow
from abacus.kernel.uow.relay import run_relay
from abacus.worker.__main__ import build_workers, publisher
from abacus_tools.synthetic.general_ledger import (
    SyntheticGl,
    build,
    intacct_general_ledger_csv,
    netsuite_general_ledger_csv,
    qbd_general_ledger_xlsx,
    qbo_general_ledger_csv,
    xero_general_ledger_xlsx,
)
from abacus_tools.synthetic.ledger_exports import qbo_trial_balance_csv

from .ledger_support import TB, YEAR_START, Json, Ledger, bucket, ledger, wire_storage
from .support import Net

BUCKET: Final = f"backfill-gl-{uuid.uuid4().hex[:10]}"
MASTER: Final = b"backfill-gl-detail-master-key-0123456789ab"
QUEUE: Final = f"backfill-gl-{uuid.uuid4().hex[:10]}"
WRITERS: Final = {
    "QuickBooks Online": qbo_general_ledger_csv,
    "Xero": xero_general_ledger_xlsx,
    "QuickBooks Desktop": qbd_general_ledger_xlsx,
    "NetSuite": netsuite_general_ledger_csv,
    "Sage Intacct": intacct_general_ledger_csv,
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


def _gl(*flaws: str) -> SyntheticGl:
    return build(TB, start=YEAR_START, flaws=flaws)


def _qbo(gl: SyntheticGl) -> bytes:
    return qbo_general_ledger_csv(gl, year=2025)


async def _tb(books: Ledger) -> None:
    """The year-end trial balance, imported for its open tier A item (SPEC-028 §6: the import
    becomes the entity's import connection and retrieval runs the pipeline for that item)."""
    await books.requested("Year-end trial balance")
    response = await books.upload_tb(qbo_trial_balance_csv(TB), "QuickBooks Online")
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "received", response.text
    await books.snapshotted()


async def _reconciled(books: Ledger, content: bytes, system: str = "QuickBooks Online") -> Json:
    response = await books.upload_gl(content, system)
    assert response.status_code == 202, response.text
    settled = await books.settled_gl()
    assert settled["status"] == "reconciled", settled
    return settled


# --- AC-2: scanned before parsing, stored with its fingerprint, parsed in isolation -------------


async def test_ac2_an_upload_answers_at_once_as_processing(books: Ledger) -> None:
    await _tb(books)
    response = await books.upload_gl(_qbo(_gl()), "QuickBooks Online")
    assert response.status_code == 202, response.text
    assert response.json()["status"] == "processing"


async def test_ac2_a_file_the_scanner_does_not_clear_is_never_parsed_or_snapshotted(
    books: Ledger,
) -> None:
    import hashlib

    await _tb(books)
    content = _qbo(_gl())
    inject_verdict(hashlib.sha256(content).hexdigest(), "infected")
    response = await books.upload_gl(content, "QuickBooks Online")
    assert response.status_code in (202, 422), response.text
    if response.status_code == 202:
        assert (await books.settled_gl())["status"] == "failed"
    assert await books.count("gl_snapshots") == 0
    assert await books.count("gl_entries") == 0


async def test_ac2_a_workbook_that_cannot_be_parsed_is_unreadable_not_a_worker_failure(
    books: Ledger,
) -> None:
    """A real xlsx container whose sheet XML is broken: the isolated parse fails, the import
    ends `failed` with `unreadable` (it never stays `processing`), and nothing is snapshotted.
    A file the upload refuses before storing it (422 `file_refused`) is also never parsed."""
    await _tb(books)
    response = await books.upload_gl(_broken_workbook(), "Xero")
    assert response.status_code in (202, 422), response.text
    if response.status_code == 422:
        assert response.json() == {"detail": "file_refused"}
    else:
        settled = await books.settled_gl()
        assert (settled["status"], settled["failure_code"]) == ("failed", "unreadable")
    assert await books.count("gl_snapshots") == 0


def _broken_workbook() -> bytes:
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["General Ledger Detail"])
    buffer = io.BytesIO()
    book.save(buffer)
    source = zipfile.ZipFile(io.BytesIO(buffer.getvalue()))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target:
        for name in source.namelist():
            data = source.read(name)
            if name.startswith("xl/worksheets/"):
                data = b"<worksheet><sheetData><row><c t='s'><v>"  # truncated XML
            target.writestr(name, data)
    return out.getvalue()


# --- AC-3: code checks coverage, balance, roll-forward, missing and extra accounts --------------


async def test_ac3_a_complete_general_ledger_reconciles_and_is_snapshotted(books: Ledger) -> None:
    await _tb(books)
    gl = _gl()
    settled = await _reconciled(books, _qbo(gl))
    assert settled["failure_code"] is None
    assert settled["line_count"] == len(gl.postings)
    snapshot = uuid.UUID(cast(str, settled["gl_snapshot_id"]))
    assert await books.count("gl_snapshots") == 1
    rows = await books.seed.rows(
        "SELECT account_code, closing FROM gl_account_balances WHERE snapshot_id = $1",
        snapshot,
    )
    closing = {str(r["account_code"]): Decimal(r["closing"]) for r in rows}
    # Closing balances roll forward to the trial balance (debit positive, credit negative).
    assert closing == {
        "1000": Decimal("52340.00"),
        "1200": Decimal("18500.00"),
        "2000": Decimal("-9750.00"),
        "3000": Decimal("-41090.00"),
        "4000": Decimal("-120000.00"),
        "5000": Decimal("24000.00"),
        "6000": Decimal("76000.00"),
    }


@pytest.mark.parametrize(
    ("flaw", "code"),
    [
        ("missing_month", "period_mismatch"),
        ("outside_period", "period_mismatch"),
        ("unbalanced", "unbalanced"),
        ("drift", "roll_forward"),
        ("missing_account", "missing_account"),
        ("extra_account", "extra_account"),
    ],
)
async def test_ac3_each_failed_check_names_its_code_and_snapshots_nothing(
    books: Ledger, flaw: str, code: str
) -> None:
    await _tb(books)
    response = await books.upload_gl(_qbo(_gl(flaw)), "QuickBooks Online")
    assert response.status_code == 202, response.text
    settled = await books.settled_gl()
    assert (settled["status"], settled["failure_code"]) == ("failed", code)
    assert settled["gl_snapshot_id"] is None
    assert await books.count("gl_snapshots") == 0
    assert await books.count("gl_entries") == 0


# --- AC-4: no trial balance yet: held, then checked when one is snapshotted ---------------------


async def test_ac4_a_general_ledger_before_its_trial_balance_waits_then_reconciles(
    books: Ledger,
) -> None:
    gl = _gl()
    response = await books.upload_gl(_qbo(gl), "QuickBooks Online")
    assert response.status_code == 202, response.text
    waiting = await books.settled_gl()
    assert waiting["status"] == "waiting_for_tb"
    assert await books.count("gl_snapshots") == 0
    await _tb(books)
    settled = await books.settled_gl_until("reconciled")
    assert settled["line_count"] == len(gl.postings)
    assert await books.count("gl_snapshots") == 1


# --- AC-5: a failure names the first accounts and the amounts; the firm sees the same -----------


async def test_ac5_a_roll_forward_failure_names_the_accounts_and_the_difference(
    books: Ledger,
) -> None:
    await _tb(books)
    response = await books.upload_gl(_qbo(_gl("drift")), "QuickBooks Online")
    assert response.status_code == 202, response.text
    settled = await books.settled_gl()
    assert settled["failure_code"] == "roll_forward"
    accounts = cast(list[Json], settled["accounts"])
    assert 1 <= len(accounts) <= 5
    for account in accounts:  # the drift is one cent between two income accounts
        assert abs(Decimal(cast(str, account["difference"]))) == Decimal("0.01")
    manager = await books.latest_gl(books.manager)
    assert manager.status_code == 200
    assert manager.json() == settled


async def test_ac5_a_missing_month_names_the_month(books: Ledger) -> None:
    await _tb(books)
    await books.upload_gl(_qbo(_gl("missing_month")), "QuickBooks Online")
    settled = await books.settled_gl()
    assert settled["failure_code"] == "period_mismatch"
    assert len(cast(list[str], settled["months"])) >= 1


async def test_ac5_a_failed_general_ledger_fulfils_nothing(books: Ledger) -> None:
    item = await books.requested("General ledger detail for the year")
    await _tb(books)
    await books.upload_gl(_qbo(_gl("unbalanced")), "QuickBooks Online")
    assert (await books.settled_gl())["status"] == "failed"
    assert await books.item_status(item) == "requested"
    linked = await books.seed.value(
        "SELECT count(*) FROM fulfilments WHERE request_item_id = $1", item
    )
    assert linked == 0


# --- AC-6 (TASK-070): the workbooks fulfil the open tier A items, never as received -------------


async def test_ac6_a_reconciled_ledger_fulfils_the_general_ledger_and_journal_items(
    books: Ledger,
) -> None:
    gl_item = await books.requested("General ledger detail")
    journals = await books.requested("Journal entries listing")
    other = await books.requested("Bank confirmation")
    await _tb(books)
    await _reconciled(books, _qbo(_gl()))
    await books.fulfilled(gl_item, journals)
    for item in (gl_item, journals):
        rows = await books.seed.rows(
            "SELECT v.method FROM fulfilments f JOIN evidence_versions v "
            "ON v.id = f.evidence_version_id WHERE f.request_item_id = $1",
            item,
        )
        assert [r["method"] for r in rows] == ["imported"], item
        # Q-03-T024: an automatic fulfilment waits for a person (DEC-09 `uploaded`).
        assert await books.item_status(item) == "uploaded"
    assert await books.item_status(other) == "requested"


# --- AC-7: the same file makes no second snapshot; a corrected file a new version ---------------


async def test_ac7_the_same_file_again_makes_no_second_snapshot(books: Ledger) -> None:
    await _tb(books)
    content = _qbo(_gl())
    first = await _reconciled(books, content)
    again = await books.upload_gl(content, "QuickBooks Online")
    assert again.status_code in (200, 202), again.text
    assert again.json()["duplicate"] is True
    assert again.json()["id"] == first["id"]
    assert await books.count("gl_snapshots") == 1


async def test_ac7_a_corrected_file_adds_a_snapshot_and_a_version_and_deletes_nothing(
    books: Ledger,
) -> None:
    item = await books.requested("General ledger detail")
    await _tb(books)
    first = await _reconciled(books, _qbo(_gl()))
    await books.fulfilled(item)
    before = await books.seed.rows(
        "SELECT evidence_version_id FROM fulfilments WHERE request_item_id = $1", item
    )
    corrected = qbo_general_ledger_csv(_gl(), company="Example Company (corrected)", year=2025)
    second = await _reconciled(books, corrected)
    assert second["gl_snapshot_id"] != first["gl_snapshot_id"]
    assert await books.count("gl_snapshots") == 2
    deadline = asyncio.get_running_loop().time() + 60
    while (
        len(
            after := await books.seed.rows(
                "SELECT evidence_version_id FROM fulfilments WHERE request_item_id = $1", item
            )
        )
        < 2
    ):
        assert asyncio.get_running_loop().time() < deadline, "no new version for the item"
        await asyncio.sleep(0.25)
    # A new version for the item; the first is kept (nothing is deleted).
    assert {r["evidence_version_id"] for r in before} < {r["evidence_version_id"] for r in after}


# --- AC-8: the app can neither update nor delete; entries only with their snapshot -------------

TABLES: Final = ("gl_snapshots", "gl_account_balances", "gl_entries")
# Literal statements per table (no SQL is built from strings).
APP_UPDATE: Final = {
    "gl_snapshots": "UPDATE gl_snapshots SET line_count = line_count",
    "gl_account_balances": "UPDATE gl_account_balances SET opening = opening",
    "gl_entries": "UPDATE gl_entries SET description = description",
}
APP_DELETE: Final = {
    "gl_snapshots": "DELETE FROM gl_snapshots",
    "gl_account_balances": "DELETE FROM gl_account_balances",
    "gl_entries": "DELETE FROM gl_entries",
}
OWNER_UPDATE: Final = {
    "gl_snapshots": "UPDATE gl_snapshots SET line_count = line_count WHERE tenant_id = $1",
    "gl_account_balances": "UPDATE gl_account_balances SET opening = opening WHERE tenant_id = $1",
    "gl_entries": "UPDATE gl_entries SET description = description WHERE tenant_id = $1",
}
OWNER_DELETE: Final = {
    "gl_snapshots": "DELETE FROM gl_snapshots WHERE tenant_id = $1",
    "gl_account_balances": "DELETE FROM gl_account_balances WHERE tenant_id = $1",
    "gl_entries": "DELETE FROM gl_entries WHERE tenant_id = $1",
}


async def _snapshot(books: Ledger) -> uuid.UUID:
    await _tb(books)
    settled = await _reconciled(books, _qbo(_gl()))
    return uuid.UUID(cast(str, settled["gl_snapshot_id"]))


async def _as_app(books: Ledger, statement: str) -> None:
    async with uow(TenantContext(books.tenant_id, "system", "q03-t023")) as tx:
        await tx.session.execute(text(statement))
        tx.record("gl_snapshot.probed", target=Target("engagement", books.site.engagement_id))


@pytest.mark.parametrize("table", TABLES)
async def test_ac8_the_app_cannot_update_a_gl_table(books: Ledger, table: str) -> None:
    await _snapshot(books)
    with pytest.raises(DBAPIError) as refused:
        await _as_app(books, APP_UPDATE[table])
    message = str(refused.value).lower()
    assert "permission denied" in message or "immutable" in message


@pytest.mark.parametrize("table", TABLES)
async def test_ac8_the_app_cannot_delete_from_a_gl_table(books: Ledger, table: str) -> None:
    await _snapshot(books)
    with pytest.raises(DBAPIError):
        await _as_app(books, APP_DELETE[table])
    assert await books.count(table) > 0


@pytest.mark.parametrize("table", TABLES)
async def test_ac8_a_trigger_refuses_an_update_even_to_the_owner(
    books: Ledger, table: str
) -> None:
    """The second layer (ADR-004): not only the app's grants; any role meets the trigger."""
    await _snapshot(books)
    with pytest.raises(asyncpg.PostgresError):
        await books.seed.run(OWNER_UPDATE[table], books.tenant_id)
    with pytest.raises(asyncpg.PostgresError):
        await books.seed.run(OWNER_DELETE[table], books.tenant_id)
    assert await books.count(table) > 0


async def test_ac8_an_entry_cannot_be_added_to_a_committed_snapshot(books: Ledger) -> None:
    snapshot = await _snapshot(books)
    before = await books.count("gl_entries")
    with pytest.raises(asyncpg.PostgresError):
        await books.seed.run(
            "INSERT INTO gl_entries (tenant_id, snapshot_id, line_no, account_code, "
            "posted_on, debit, credit, source_ref) "
            "VALUES ($1, $2, 999999, '1000', '2025-06-30', 1, 0, 'row 999999')",
            books.tenant_id,
            snapshot,
        )
    assert await books.count("gl_entries") == before


# --- TASK-071 and Q-03-T024: each of the five formats round-trips -------------------------------


@pytest.mark.parametrize("system", list(WRITERS))
async def test_ac3_each_of_the_five_formats_round_trips_to_a_reconciled_snapshot(
    books: Ledger, system: str
) -> None:
    await _tb(books)
    gl = _gl()
    settled = await _reconciled(books, WRITERS[system](gl, year=2025), system)
    assert settled["line_count"] == len(gl.postings)
    snapshot = uuid.UUID(cast(str, settled["gl_snapshot_id"]))
    totals = await books.seed.rows(
        "SELECT sum(debit) AS d, sum(credit) AS c, count(*) AS n FROM gl_entries "
        "WHERE snapshot_id = $1",
        snapshot,
    )
    assert totals[0]["n"] == len(gl.postings)
    assert Decimal(totals[0]["d"]) == sum((p.debit for p in gl.postings), Decimal(0))
    assert Decimal(totals[0]["c"]) == sum((p.credit for p in gl.postings), Decimal(0))
