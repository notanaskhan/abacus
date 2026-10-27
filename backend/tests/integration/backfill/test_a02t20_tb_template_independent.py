# ac-test-author: ayushkbhatia
"""A-02-T20 (TASK-1473), the import hook half: the Accrued trial balance template (A-02 §2.2
item 3, R-7, DEC-610; SPEC-028's format list as "Trial balance template").

The row's acceptance: the suite fails when a template that does not foot is accepted. The
template is an XLSX with `Account` · `Account name` · `Debit` · `Credit`, a `Period end:` line
and a `Total` row (A-02-T22); SPEC-028 AC-5 and AC-6 give the refusals ("Debits and credits
differ by $1,250.00", the wrong period, not the format chosen) and say a failed check snapshots
nothing. A template that foots becomes a snapshot of source kind `import` (SPEC-333 AC-32) that
AUD-06 can adopt. Client-visible words never say "Accrued" (DEC-01, ADR-133).

Boundary: `create_app()` over HTTP as the engagement partner (the import routes of SPEC-028), the
compose S3 image and the real worker pools on a Temporal dev server, as the Q-03-T024 back-fill
runs them (`ledger_support.py`). Workbooks are written here with openpyxl from literals.
"""

from __future__ import annotations

import asyncio
import io
import uuid
from collections.abc import AsyncGenerator, AsyncIterator, Iterator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import date
from typing import Final, cast

import pytest
from openpyxl import Workbook
from temporalio.client import Client
from temporalio.worker import Worker
from types_boto3_s3 import S3Client

from abacus.kernel.config import settings
from abacus.kernel.scanning import forget_injected
from abacus.kernel.temporal import configure_temporal_client, data_converter
from abacus.kernel.uow.relay import run_relay
from abacus.worker.__main__ import build_workers, publisher
from abacus_tools.synthetic.ledger_exports import xero_trial_balance_xlsx

from .ledger_support import TB, Ledger, bucket, ledger, wire_storage
from .support import Net

BUCKET: Final = f"a02t20-tpl-{uuid.uuid4().hex[:10]}"
MASTER: Final = b"a02t20-template-master-key-0123456789ab"
QUEUE: Final = f"a02t20-tpl-{uuid.uuid4().hex[:10]}"
SYSTEM: Final = "Trial balance template"
Row = tuple[str, str, str | None, str | None]
# Debits 170,840.00 = credits 170,840.00 (the same literal books as ledger_support.TB).
BALANCED: Final[tuple[Row, ...]] = (
    ("1000", "Checking", "52340.00", None),
    ("1200", "Accounts Receivable", "18500.00", None),
    ("2000", "Accounts Payable", None, "9750.00"),
    ("3000", "Retained Earnings", None, "41090.00"),
    ("4000", "Revenue", None, "120000.00"),
    ("5000", "Rent", "24000.00", None),
    ("6000", "Wages", "76000.00", None),
)


def template(
    rows: Sequence[Row], *, period_end: date = date(2025, 12, 31), total: bool = True
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["Trial balance"])
    sheet.append([f"Period end: {period_end.isoformat()}"])
    sheet.append([])
    sheet.append(["Account", "Account name", "Debit", "Credit"])
    for code, name, debit, credit in rows:
        sheet.append(
            [code, name, float(debit) if debit else None, float(credit) if credit else None]
        )
    if total:
        debit = sum(float(r[2]) for r in rows if r[2])
        credit = sum(float(r[3]) for r in rows if r[3])
        sheet.append(["Total", None, debit, credit])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


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


async def test_ac24_the_template_is_offered_with_steps_and_never_says_accrued(
    books: Ledger,
) -> None:
    response = await books.net.call("GET", f"{books.base}/formats", books.partner)
    assert response.status_code == 200, response.text
    [found] = [f for f in cast(list[dict[str, object]], response.json()) if f["system"] == SYSTEM]
    words = [found["system"], *cast(list[str], found["steps"])]  # what a client reads
    assert "accrued" not in " ".join(cast(list[str], words)).lower()
    assert found.get("steps")


async def test_ac24_a_template_that_does_not_foot_is_refused_with_its_difference(
    books: Ledger,
) -> None:
    item = await books.requested("Year-end trial balance")
    off = (*BALANCED[:-1], ("6000", "Wages", "77250.00", None))  # debits exceed by 1,250.00
    response = await books.upload_tb(template(off, total=False), SYSTEM)
    assert response.status_code in (201, 422), response.text
    if response.status_code == 201:
        body = cast(dict[str, object], response.json())
        assert body["status"] == "failed"
        assert body["failure_code"] == "unbalanced"
        assert body["difference"] is not None
        assert abs(float(cast(str, body["difference"]))) == 1250.00
    await asyncio.sleep(1.0)  # give a wrongly started pipeline time to snapshot
    assert await books.count("ledger_snapshots") == 0
    assert await books.item_status(item) == "requested"


def _with_total(label_column: int) -> bytes:
    """The balanced lines under a Total row that claims 171,000.00 a side (they carry
    170,840.00), the label in the given column (0 Account, 1 Account name)."""
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["Period end: 2025-12-31"])
    sheet.append(["Account", "Account name", "Debit", "Credit"])
    for code, name, debit, credit in BALANCED:
        sheet.append(
            [code, name, float(debit) if debit else None, float(credit) if credit else None]
        )
    label: list[str | None] = [None, None]
    label[label_column] = "Total"
    sheet.append([*label, 171000.0, 171000.0])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


async def _refused(books: Ledger, content: bytes) -> None:
    response = await books.upload_tb(content, SYSTEM)
    assert response.status_code in (201, 422), response.text
    if response.status_code == 201:
        assert response.json()["status"] == "failed", response.text
    await asyncio.sleep(1.0)
    assert await books.count("ledger_snapshots") == 0


async def test_ac24_a_total_row_that_disagrees_with_the_lines_is_refused(books: Ledger) -> None:
    """SPEC-028 AC-5: the file's own total row is the control total."""
    await _refused(books, _with_total(1))


@pytest.mark.xfail(
    strict=True,
    reason="A Total row labelled in the Account column is dropped, not read as the control "
    "total, so a template whose Total disagrees with its lines is accepted (totals from lines); "
    "recorded in work/tasks/TASK-1473-a02t20-ledger-tb-independent.md (ED number requested)",
)
async def test_ac24_a_total_row_labelled_in_the_account_column_is_still_the_control(
    books: Ledger,
) -> None:
    await _refused(books, _with_total(0))


async def test_ac24_a_template_for_another_period_is_refused(books: Ledger) -> None:
    response = await books.upload_tb(template(BALANCED, period_end=date(2025, 11, 30)), SYSTEM)
    assert response.status_code in (201, 422), response.text
    if response.status_code == 201:
        assert response.json()["status"] == "failed", response.text
    await asyncio.sleep(1.0)
    assert await books.count("ledger_snapshots") == 0


async def test_ac24_another_systems_file_chosen_as_the_template_is_refused(
    books: Ledger,
) -> None:
    response = await books.upload_tb(xero_trial_balance_xlsx(TB), SYSTEM)
    assert response.status_code in (201, 422), response.text
    if response.status_code == 201:
        assert response.json()["status"] == "failed", response.text
    await asyncio.sleep(1.0)
    assert await books.count("ledger_snapshots") == 0


async def test_ac32_a_template_that_foots_becomes_an_import_snapshot(books: Ledger) -> None:
    await books.requested("Year-end trial balance")
    response = await books.upload_tb(template(BALANCED), SYSTEM)
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "received", response.text
    await books.snapshotted()
    [row] = await books.seed.rows(
        "SELECT source_kind, label, total_debit, total_credit, line_count "
        "FROM ledger_snapshots WHERE tenant_id = $1",
        books.tenant_id,
    )
    assert row["source_kind"] == "import"
    assert row["label"] == "standard"
    assert str(row["total_debit"]) == "170840.00" == str(row["total_credit"])
    assert row["line_count"] == 7
