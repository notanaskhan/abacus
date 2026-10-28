# ac-test-author: ayushkbhatia
"""Q-03-T524: back-fill of TASK-053, SPEC-028 AC-3, black-box from the spec.

AC-3: an uploaded export is stored write-once with its fingerprint, malware-scanned before
anything parses it, and recorded as a ledger import; a file that is not scanned clean is refused
and nothing is parsed, snapshotted or fulfilled.

AC-2, AC-4, AC-5, AC-6 and AC-8 of SPEC-028 hold for TASK-053's formats in
`test_ledger_formats.py` (Q-03-T024, same author); AC-7 in
`tests/unit/connections/test_q03t524_import_capabilities.py`; AC-1, AC-2, AC-6 and AC-9 on the
screen in `apps/web/src/legacy/q03t524ledgerimport.test.tsx`.

Boundary: `create_app()` over HTTP as the engagement partner, the compose S3 image and the local
scanner (EICAR is refused), as `test_ledger_formats.py` wires them. No worker runs: a refused file
must never reach one, and a clean file's row is written by the route.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from typing import Final

import pytest
from types_boto3_s3 import S3Client

from abacus.kernel.scanning import EICAR, forget_injected
from abacus_tools.synthetic.ledger_exports import qbo_trial_balance_csv

from .ledger_support import TB, Ledger, bucket, ledger, wire_storage
from .support import Net

BUCKET: Final = f"backfill-t524-{uuid.uuid4().hex[:10]}"
MASTER: Final = b"backfill-t524-storage-master-key-012345"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> S3Client:
    return bucket(s3_settings, BUCKET)


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    forget_injected()
    yield from wire_storage(raw, BUCKET, MASTER)
    forget_injected()


@pytest.fixture
async def books(net: Net) -> Ledger:
    return await ledger(net, flags=("ledger.import",))


async def _imports(books: Ledger) -> list[dict[str, object]]:
    rows = await books.seed.rows(
        "SELECT fingerprint, size_bytes, scan_status, status, storage_version_id "
        "FROM ledger_imports WHERE tenant_id = $1",
        books.tenant_id,
    )
    return [dict(r) for r in rows]


async def test_ac3_a_clean_export_is_recorded_as_an_import_with_its_fingerprint(
    books: Ledger,
) -> None:
    content = qbo_trial_balance_csv(TB)
    response = await books.upload_tb(content, "QuickBooks Online")
    assert response.status_code == 201, response.text
    rows = await _imports(books)
    assert len(rows) == 1
    row = rows[0]
    assert row["fingerprint"] == hashlib.sha256(content).hexdigest()
    assert row["size_bytes"] == len(content)
    assert row["scan_status"] == "clean"
    assert row["storage_version_id"]  # a versioned, write-once object


async def test_ac3_a_file_the_scanner_refuses_is_never_parsed_or_fulfilled(books: Ledger) -> None:
    item = await books.requested("Year-end trial balance")
    response = await books.upload_tb(EICAR, "QuickBooks Online")
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "file_refused"
    assert await books.count("ledger_snapshots") == 0
    assert (
        await books.seed.value("SELECT count(*) FROM fulfilments WHERE request_item_id = $1", item)
        == 0
    )
    assert all(r["scan_status"] != "clean" for r in await _imports(books))
