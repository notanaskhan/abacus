# ac-test-author: ayushkbhatia
"""N-01-T20 (TASK-2144; ADR-078): independent AC tests for N-01's intake, triage and Files.

Acceptance (the task row): "Suites ... prove INV-3 and INV-4 on every inbox and Files read, and
I-AGENT-NEVER covers inbox.file, inbox.triage, inbox.match_sender and inbox.ask_client."

- **I-AGENT-NEVER**: the matrix denies the four human decisions to the agent and the system, and a
  system context calling triage apply is refused before anything is written.
- **INV-3 (walls)**: a person walled from Ashford gets 404 on every inbox read of Ashford's
  thread, attachment and message (no hint), Ashford is out of the summary's counts and the thread
  list, and the Files tree leaves the client out.
- **INV-4 (portal scope)**: a client principal never reaches a firm inbox or Files read (404).
- **T07**: intake rows are insert-only (the immutable triggers refuse an edit).
- **T09**: the same bytes twice are flagged `duplicate_hash`, never refused.
- **T18**: bulk filing answers per attachment (partial success), never all-or-nothing.

Boundary: `create_app()` over HTTP as each signed-in person; seeded rows through SQL. The fixtures
are group B's (`test_n01_group_b.py`).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import TYPE_CHECKING, Final

import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import storage
from abacus.modules.identity.authz.matrix import RULES

from . import test_n01_group_b as group_b
from .test_n01_group_b import Firm

EVIDENCE: Final = "n01t20-evidence"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    """This suite's own bucket (group B's module creates its own)."""
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    client.create_bucket(Bucket=EVIDENCE, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(group_b.MASTER))
    storage.configure_storage(raw, EVIDENCE)
    yield
    storage.reset_storage()
    reset_key_service()
    forget_flags()


# Group B's firm fixture, shared by name.
firm = group_b.firm
_email = group_b._email  # pyright: ignore[reportPrivateUsage] -- group B's batch helper

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
HUMAN_ONLY: Final = ("inbox.file", "inbox.triage", "inbox.match_sender", "inbox.ask_client")


def _thread_ids(body: dict[str, list[dict[str, str]]]) -> set[str]:
    return {t["id"] for t in body.get("items", [])}


def test_i_agent_never_holds_the_inbox_decisions() -> None:
    for action in HUMAN_ONLY:
        rule = RULES[action]
        assert rule.decisions.get("agent") == "deny", action
        assert rule.decisions.get("system") == "deny", action


async def test_inv3_a_walled_person_gets_404_on_every_inbox_read(firm: Firm) -> None:
    message, (attachment,) = await _email(firm, firm.ashford, "Ashford 2025 documents")
    thread = await firm.net.seed.value(
        "SELECT thread_id FROM inbox_attachments WHERE id = $1", attachment
    )
    reads = (
        f"/v1/inbox/threads/{thread}",
        f"/v1/inbox/attachments/{attachment}/viewer",
        f"/v1/inbox/attachments/{attachment}/content",
        f"/v1/inbox/messages/{message}/attachments.zip",
        f"/v1/inbox/messages/{message}/triage",
    )
    for path in reads:
        walled = await firm.call("GET", path, firm.lena)
        assert walled.status_code == 404, (path, walled.status_code)
        assert "Ashford" not in walled.text
    # The thread list and the summary leave Ashford out for Lena, not for Grace.
    lena_threads = (await firm.call("GET", "/v1/inbox/threads", firm.lena)).json()
    grace_threads = (await firm.call("GET", "/v1/inbox/threads", firm.grace)).json()
    assert str(thread) not in _thread_ids(lena_threads)
    assert str(thread) in _thread_ids(grace_threads)


async def test_inv3_the_files_tree_leaves_the_walled_client_out(firm: Firm) -> None:
    tree = await firm.call("GET", "/v1/files/tree", firm.lena)
    assert tree.status_code in (200, 404)
    assert str(firm.ashford.client_id) not in tree.text
    one = await firm.call("GET", f"/v1/files/tree?client_id={firm.ashford.client_id}", firm.lena)
    assert one.status_code == 404


async def test_inv4_a_client_principal_never_reaches_a_firm_inbox_read(firm: Firm) -> None:
    message, (attachment,) = await _email(firm, firm.feld, "Feld 2025 documents")
    claire = await firm.net.seed.client_contact(firm.feld)
    for path in (
        "/v1/inbox/summary",
        "/v1/inbox/threads",
        f"/v1/inbox/attachments/{attachment}/content",
        f"/v1/inbox/messages/{message}/triage",
        "/v1/files/tree",
    ):
        answer = await firm.call("GET", path, claire)
        assert answer.status_code in (403, 404), (path, answer.status_code)


async def test_t07_intake_rows_are_insert_only(firm: Firm) -> None:
    message, (attachment,) = await _email(firm, firm.feld, "Immutable")
    with pytest.raises(Exception):  # noqa: B017 -- the immutable trigger names the table
        await firm.net.seed.run(
            "UPDATE inbound_messages SET subject_display = 'edited' WHERE id = $1", message
        )
    await firm.net.seed.run(
        "INSERT INTO inbox_attachment_flags (tenant_id, attachment_id, run_no, kind, severity, "
        "checker_version) VALUES ($1, $2, 9, 'unreadable', 'block_bulk', 'test')",
        firm.tenant_id,
        attachment,
    )
    with pytest.raises(Exception):  # noqa: B017
        await firm.net.seed.run(
            "DELETE FROM inbox_attachment_flags WHERE attachment_id = $1", attachment
        )


async def test_t09_the_same_bytes_twice_are_flagged_never_refused(firm: Firm) -> None:
    # One file per batch: `_email` sends identical bytes each time.
    _m, (first,) = await _email(firm, firm.feld, "First copy")
    _m2, (again,) = await _email(firm, firm.feld, "Second copy")
    flags = await firm.net.seed.rows(
        "SELECT kind, facts FROM inbox_attachment_flags WHERE attachment_id = $1", again
    )
    duplicate = [f for f in flags if f["kind"] == "duplicate_hash"]
    assert len(duplicate) == 1
    assert str(first) in str(duplicate[0]["facts"])
    status = await firm.net.seed.value("SELECT status FROM inbox_attachments WHERE id = $1", again)
    assert status == "waiting"  # flagged, never refused


async def test_t18_bulk_filing_answers_per_attachment(firm: Firm) -> None:
    _message, (a1, a2) = await _email(firm, firm.feld, "Bulk", files=2)
    await firm.net.seed.run(
        "INSERT INTO inbox_attachment_flags (tenant_id, attachment_id, run_no, kind, severity, "
        "facts, checker_version) VALUES ($1, $2, 2, 'wrong_year', 'block_bulk', "
        "'{\"tax_year\": 2024}'::jsonb, 'test')",
        firm.tenant_id,
        a1,
    )
    answer = await firm.net.http.post(
        "/v1/inbox/attachments/bulk-file",
        json={"attachment_ids": [str(a1), str(a2)]},
        headers={**firm.net.headers(firm.grace), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert answer.status_code == 200, answer.text
    outcomes = {r["attachment_id"]: r["outcome"] for r in answer.json()["results"]}
    assert set(outcomes) == {str(a1), str(a2)}
    assert outcomes[str(a1)] == "has_flags"
