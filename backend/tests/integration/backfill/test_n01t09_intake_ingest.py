# ac-test-author: ayushkbhatia
"""N-01-T09 (TASK-1731; N-01 §4.3; ADR-210; DEC-821): intake ingest.

Acceptance (the task row): "A staff-logged batch creates one thread with its attachments as New
or Waiting, and a scanner outage stores nothing."

Also: an email replying to a held message joins its thread; a live sender rule matches; the same
file again is flagged `duplicate_hash`, not refused; only the person who logged a batch adds to
it; the note is sealed and the sender kept as an HMAC; a replay answers the same thread.

Boundary: `create_app()` over HTTP for the staff routes; `communications.api` for email.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, cast

import httpx
import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.scanning import inject_verdict
from abacus.kernel.storage import s3_client
from abacus.modules.communications.api import Inbound, record_inbound_message
from abacus.modules.communications.deliveries import address_hash
from abacus.modules.evidence import storage

from .support import Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response or request body as the contract shapes it
FLAG: Final = "inbox.firm_intake"
EVIDENCE: Final = "n01t09-evidence"
MASTER: Final = b"n01t09-independent-master-key-0123456789"
W2: Final = b"%PDF-1.7\n% W-2 2026\n%%EOF\n"
K1: Final = b"%PDF-1.7\n% K-1 2026\n%%EOF\n"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
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
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    yield
    storage.reset_storage()
    reset_key_service()
    forget_flags()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    grace: Person  # on the Intake team
    henry: Person  # also on it
    site: Site

    async def log(self, who: Person, body: Body, key: str = "log-1") -> httpx.Response:
        return await self.net.http.post(
            "/v1/inbox/intake",
            json=body,
            headers={**self.net.headers(who), "Idempotency-Key": key},
        )

    async def file(
        self, who: Person, message: str, content: bytes, name: str, key: str
    ) -> httpx.Response:
        return await self.net.http.post(
            f"/v1/inbox/intake/{message}/files",
            params={"filename": name},
            content=content,
            headers={
                **self.net.headers(who),
                "Idempotency-Key": key,
                "Content-Type": "application/octet-stream",
            },
        )

    async def count(self, table: str) -> int:
        return int(str(await self.net.seed.value(_COUNTS[table], self.tenant_id)))


_COUNTS: Final = {
    "inbox_threads": "SELECT count(*) FROM inbox_threads WHERE tenant_id = $1",
    "inbound_messages": "SELECT count(*) FROM inbound_messages WHERE tenant_id = $1",
    "inbox_attachments": "SELECT count(*) FROM inbox_attachments WHERE tenant_id = $1",
}


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'N-01-T09')",
        tenant,
        FLAG,
    )
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant)
    henry = await seed.person(tenant)
    site = await seed.site(tenant, admin.user_id, "Feld")
    team = await seed.value(
        "INSERT INTO teams (tenant_id, name, kind) VALUES ($1, 'Intake', 'intake') RETURNING id",
        tenant,
    )
    for who in (grace, henry):
        await seed.run(
            "INSERT INTO team_rosters (tenant_id, team_id, user_id) VALUES ($1, $2, $3)",
            tenant,
            team,
            who.user_id,
        )
    return Firm(net, tenant, admin, grace, henry, site)


def _batch(firm: Firm, matched: bool = True) -> Body:
    body: Body = {
        "received_via": "mail",
        "received_at": "2027-03-02",
        "subject": "Feld household 2026 tax documents",
        "from_display": "Lena Feld",
        "note": "Dropped off at the front desk",
    }
    if matched:
        body["client_id"] = str(firm.site.client_id)
    return body


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_a_staff_logged_batch_creates_one_thread_with_waiting_attachments(
    firm: Firm,
) -> None:
    made = await firm.log(firm.grace, _batch(firm))
    assert made.status_code == 201, made.text
    message = cast(Body, made.json())["message_id"]
    for n, (content, name) in enumerate(((W2, "W-2.pdf"), (K1, "K-1.pdf"))):
        response = await firm.file(firm.grace, message, content, name, f"file-{n}")
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "waiting"
    assert await firm.count("inbox_threads") == 1
    assert await firm.count("inbound_messages") == 1
    assert await firm.count("inbox_attachments") == 2


async def test_ac_an_unmatched_batch_holds_new_attachments(firm: Firm) -> None:
    made = await firm.log(firm.grace, _batch(firm, matched=False))
    message = cast(Body, made.json())["message_id"]
    response = await firm.file(firm.grace, message, W2, "W-2.pdf", "file-0")
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "new"


async def test_ac_a_scanner_outage_stores_nothing(firm: Firm, raw: S3Client) -> None:
    made = await firm.log(firm.grace, _batch(firm))
    message = cast(Body, made.json())["message_id"]
    down = b"%PDF-1.7\n% scanner down\n%%EOF\n"
    inject_verdict(hashlib.sha256(down).hexdigest(), "error")
    response = await firm.file(firm.grace, message, down, "W-2.pdf", "file-0")
    assert response.status_code in (422, 503)
    assert await firm.count("inbox_attachments") == 0
    listed = raw.list_objects_v2(Bucket=EVIDENCE, Prefix=f"{firm.tenant_id}/")
    assert listed.get("KeyCount", 0) == 0


# --- The rest of the row ------------------------------------------------------------------------


async def test_the_same_file_again_is_flagged_not_refused(firm: Firm) -> None:
    made = await firm.log(firm.grace, _batch(firm))
    message = cast(Body, made.json())["message_id"]
    first = await firm.file(firm.grace, message, W2, "W-2.pdf", "file-0")
    again = await firm.file(firm.grace, message, W2, "W-2 copy.pdf", "file-1")
    assert first.status_code == again.status_code == 201
    flag = await firm.net.seed.value(
        "SELECT kind FROM inbox_attachment_flags WHERE attachment_id = $1",
        uuid.UUID(again.json()["attachment_id"]),
    )
    assert flag == "duplicate_hash"


async def test_only_the_person_who_logged_a_batch_adds_to_it(firm: Firm) -> None:
    made = await firm.log(firm.grace, _batch(firm))
    message = cast(Body, made.json())["message_id"]
    response = await firm.file(firm.henry, message, W2, "W-2.pdf", "file-0")
    assert response.status_code == 404


async def test_a_replay_answers_the_same_thread(firm: Firm) -> None:
    first = await firm.log(firm.grace, _batch(firm))
    again = await firm.log(firm.grace, _batch(firm))
    assert first.json() == again.json()
    assert await firm.count("inbox_threads") == 1


async def test_the_note_is_sealed_and_the_sender_kept_as_an_hmac(firm: Firm) -> None:
    tenant = TenantContext(firm.tenant_id, "system", "test:intake")
    made = await record_inbound_message(
        tenant,
        Inbound(
            channel="email",
            sender_display="Lena Feld",
            sender_address="Lena.Feld@example.test",
            subject="1099s",
            body="Here are the 1099s",
            internet_message_id="<a@example.test>",
            received_at=datetime(2027, 3, 2, 9, tzinfo=UTC),
        ),
    )
    row = await firm.net.seed.rows(
        "SELECT body_sealed, sender_address_hmac FROM inbound_messages WHERE id = $1",
        made.message_id,
    )
    assert b"1099s" not in bytes(row[0]["body_sealed"])
    assert row[0]["sender_address_hmac"] == address_hash("lena.feld@example.test").hex()
    reply = await record_inbound_message(
        tenant,
        Inbound(
            channel="email",
            sender_display="Lena Feld",
            sender_address="lena.feld@example.test",
            subject="Re: 1099s",
            in_reply_to="<a@example.test>",
            received_at=datetime(2027, 3, 3, 9, tzinfo=UTC),
        ),
    )
    assert reply.thread_id == made.thread_id


async def test_a_live_sender_rule_matches_the_client(firm: Firm) -> None:
    await firm.net.seed.run(
        "INSERT INTO inbox_sender_rules (tenant_id, address_hmac, address_sealed, client_id, "
        "created_by) VALUES ($1, $2, '\\x00', $3, $4)",
        firm.tenant_id,
        address_hash("owen@example.test").hex(),
        firm.site.client_id,
        firm.grace.user_id,
    )
    made = await record_inbound_message(
        TenantContext(firm.tenant_id, "system", "test:intake"),
        Inbound(
            channel="email",
            sender_display="Owen Calder",
            sender_address="OWEN@example.test",
            subject="Receipts",
            received_at=datetime(2027, 3, 2, 9, tzinfo=UTC),
        ),
    )
    assert made.client_id == firm.site.client_id


async def test_a_walled_intake_member_cannot_log_for_that_client(firm: Firm) -> None:
    await firm.net.wall(firm.admin, firm.henry, firm.site)
    refused = await firm.log(firm.henry, _batch(firm))
    assert refused.status_code == 404
    assert await firm.count("inbox_threads") == 0
