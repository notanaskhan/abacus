# ac-test-author: ayushkbhatia
"""N-01-T25 (TASK-2333; ADR-078): independent AC tests for N-01-T17's flags and their interplay
with N-01-T18, written from the acceptance text and SPEC-380 AC-10, AC-12, AC-16 and AC-17.

Acceptance (the task row): "Suites are merged and green, the 2024 Feld 1095-C is flagged wrong
year and duplicate through the public API, and no matcher output path files, ignores, holds or
supersedes." The matcher half is `test_n01t25_matcher_independent.py`.

- **Through the public API:** the 2024 Feld 1095-C reads `wrong_year` and `duplicate_hash` on
  `GET /v1/inbox/threads/{id}`; flag facts carry years, identifiers and masked last-4 only.
- **Forced Hold (T18):** a TIN mismatch opens the card on Hold, forced; filing it answers 409
  `flag_requires_hold` and writes nothing.
- **Bulk refusal (AC-17):** a flagged attachment answers `has_flags` in a bulk file and stays put.
- **Cross-client containment:** filing one client's attachment to another client's request answers
  409 `destination_outside_client` and writes nothing.

Boundary: `create_app()` over HTTP as a signed-in firm person; the email arrives through the
communications API and the upload and classify steps as the worker runs them; seeded rows and
outcomes through SQL.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.communications.api import (
    Inbound,
    TriageInput,
    add_attachment,
    record_inbound_message,
)
from abacus.modules.communications.deliveries import address_hash
from abacus.modules.communications.triage_classify import attachment_classified
from abacus.modules.evidence import storage
from abacus.modules.evidence.api import INTAKE, UploadInput, pii_scan_upload, words_upload
from abacus.modules.evidence.api import process_upload as extract_upload
from abacus_tools.synthetic.documents import positioned_pdf

from .support import Net, Person, Site

if TYPE_CHECKING:
    import httpx
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
EVIDENCE: Final = "n01t25-evidence"
MASTER: Final = b"n01t25-independent-master-key-012345678"
FULL_TIN: Final = re.compile(r"\d{3}-?\d{2}-?\d{4}")


def _form_1095c(year: int) -> bytes:
    return positioned_pdf(
        [
            [
                (50, 740, "Form 1095-C Employer-Provided Health Insurance Offer and Coverage"),
                (50, 720, "Employee: Claire Feld"),
                (50, 700, f"Tax year {year}"),
            ]
        ]
    )


W2C: Final = positioned_pdf(
    [
        [
            (50, 740, "Form W-2c Corrected Wage and Tax Statement"),
            (50, 720, "Tax year 2025"),
            (50, 700, "Employee's correct SSN 900-00-7713"),
        ]
    ]
)


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


class Firm:
    def __init__(self, net: Net, tenant: uuid.UUID, grace: Person, feld: Site) -> None:
        self.net = net
        self.tenant = tenant
        self.grace = grace
        self.feld = feld

    async def receive(self, site: Site, file_name: str, content: bytes) -> uuid.UUID:
        """One email from `site`'s client with one file, through upload and classify."""
        system = TenantContext(self.tenant, "system", "test.n01t25")
        address = f"sender+{uuid.uuid4().hex[:6]}@example.com"
        await self.net.seed.run(
            "INSERT INTO inbox_sender_rules (tenant_id, address_hmac, address_sealed, "
            "client_id, created_by) VALUES ($1, $2, '\\x00', $3, $4)",
            self.tenant,
            address_hash(address).hex(),
            site.client_id,
            self.grace.user_id,
        )
        made = await record_inbound_message(
            system,
            Inbound(
                channel="email",
                sender_display="Sender",
                subject="2025 tax documents",
                received_at=datetime.now(UTC),
                body="Attached.",
                sender_address=address,
            ),
        )
        got = await add_attachment(system, made.message_id, file_name=file_name, content=content)
        given = UploadInput(str(self.tenant), INTAKE, str(got.attachment_id))
        await extract_upload(given)
        await words_upload(given)
        await pii_scan_upload(given)
        await attachment_classified(TriageInput(str(self.tenant), str(got.attachment_id)))
        return got.attachment_id

    async def message_of(self, attachment: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.net.seed.value(
                "SELECT message_id FROM inbox_attachments WHERE id = $1", attachment
            ),
        )

    async def thread_of(self, attachment: uuid.UUID) -> uuid.UUID:
        return cast(
            uuid.UUID,
            await self.net.seed.value(
                "SELECT thread_id FROM inbox_attachments WHERE id = $1", attachment
            ),
        )

    async def post(self, path: str, body: dict[str, object]) -> httpx.Response:
        return await self.net.http.post(
            path,
            json=body,
            headers={**self.net.headers(self.grace), "Idempotency-Key": str(uuid.uuid4())},
        )

    async def decisions(self, attachment: uuid.UUID) -> int:
        return int(
            str(
                await self.net.seed.value(
                    "SELECT count(*) FROM triage_decisions WHERE attachment_id = $1", attachment
                )
            )
        )


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'inbox.firm_intake', 'true', 'test-seed', 'N-01-T25')",
        tenant,
    )
    grace = await seed.person(tenant, "firm_admin")
    team = await seed.value(
        "INSERT INTO teams (tenant_id, name, kind) VALUES ($1, 'Intake', 'intake') RETURNING id",
        tenant,
    )
    await seed.run(
        "INSERT INTO team_rosters (tenant_id, team_id, user_id) VALUES ($1, $2, $3)",
        tenant,
        team,
        grace.user_id,
    )
    feld = await seed.site(tenant, grace.user_id, "Feld")
    # The TY2025 return: the year Feld's work is for.
    await seed.run(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, period_start, "
        "period_end, created_by) VALUES ($1, $2, $3, 'tax_return', 'TY2025 Form 1040', "
        "'2025-01-01', '2025-12-31', $4)",
        tenant,
        feld.engagement_id,
        feld.client_id,
        grace.user_id,
    )
    forget_flags()
    return Firm(net, tenant, grace, feld)


async def _filed_before(firm: Firm, content: bytes) -> uuid.UUID:
    """The same bytes, already filed as a version of Feld's evidence (versions are immutable)."""
    fingerprint = hashlib.sha256(content).hexdigest()
    return cast(
        uuid.UUID,
        await firm.net.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) SELECT tenant_id, engagement_id, evidence_item_id, 2, $2, $3, 'v1', "
            "$4, 'application/pdf', 'upload', 'uploaded' FROM evidence_versions WHERE id = $1 "
            "RETURNING id",
            firm.feld.version_id,
            fingerprint,
            f"tenants/{firm.tenant}/sha256/{fingerprint}",
            len(content),
        ),
    )


def _attachment(detail: dict[str, object], attachment: uuid.UUID) -> dict[str, object]:
    messages = cast(list[dict[str, object]], detail["messages"])
    found = [
        a
        for m in messages
        for a in cast(list[dict[str, object]], m["attachments"])
        if a["id"] == str(attachment)
    ]
    assert len(found) == 1, detail
    return found[0]


async def test_ac_the_2024_feld_1095c_reads_wrong_year_and_duplicate_on_the_api(
    firm: Firm,
) -> None:
    content = _form_1095c(2024)
    earlier = await _filed_before(firm, content)
    attachment = await firm.receive(firm.feld, "Feld_1095C_2024.pdf", content)
    thread = await firm.thread_of(attachment)

    got = await firm.net.call("GET", f"/v1/inbox/threads/{thread}", firm.grace)
    assert got.status_code == 200, got.text
    flags = {
        str(f["kind"]): f
        for f in cast(list[dict[str, object]], _attachment(got.json(), attachment)["flags"])
    }
    assert {"wrong_year", "duplicate_hash"} <= set(flags)
    wrong = cast(dict[str, object], flags["wrong_year"]["facts"])
    assert (wrong["tax_year"], wrong["expected_year"]) == (2024, 2025)
    duplicate = flags["duplicate_hash"]
    assert str(earlier) in (
        str(duplicate["ref_evidence_version_id"]),
        str(cast(dict[str, object], duplicate["facts"]).get("duplicate_of_version")),
    )
    # AC-10: facts hold identifiers, years and masked last-4 only.
    for flag in flags.values():
        assert FULL_TIN.search(str(flag["facts"])) is None


async def test_ac_a_tin_mismatch_forces_hold_and_filing_it_is_refused(firm: Firm) -> None:
    await firm.net.seed.run(
        "UPDATE client_entities SET tin_sealed = '\\x00', tin_last4 = '7731', tin_kind = 'ssn', "
        "tin_status = 'on_file', tin_fingerprint = $2 WHERE id = $1",
        firm.feld.entity_id,
        hashlib.sha256(b"n01t25-collins").digest(),
    )
    attachment = await firm.receive(firm.feld, "Collins_W-2c_2025.pdf", W2C)
    message = await firm.message_of(attachment)

    bundle = await firm.net.call("GET", f"/v1/inbox/messages/{message}/triage", firm.grace)
    assert bundle.status_code == 200, bundle.text
    [card] = [
        c
        for c in cast(list[dict[str, object]], bundle.json()["attachments"])
        if cast(dict[str, object], c["attachment"])["id"] == str(attachment)
    ]
    defaults = cast(dict[str, object], card["defaults"])
    assert (defaults["decision"], defaults["decision_forced"]) == ("hold", True)
    flags = cast(list[dict[str, object]], cast(dict[str, object], card["attachment"])["flags"])
    mismatch = [f for f in flags if f["kind"] == "tin_mismatch"]
    assert mismatch and mismatch[0]["severity"] == "force_hold"
    assert FULL_TIN.search(str(mismatch[0]["facts"])) is None  # masked last-4 only

    filed = await firm.post(
        f"/v1/inbox/messages/{message}/triage/apply",
        {
            "decisions": [
                {
                    "attachment_id": str(attachment),
                    "decision": "file",
                    "destination": {"kind": "request", "id": str(firm.feld.item_id)},
                }
            ]
        },
    )
    assert filed.status_code == 409, filed.text
    assert filed.json()["detail"] == "flag_requires_hold"
    assert await firm.decisions(attachment) == 0
    status = await firm.net.seed.value(
        "SELECT status FROM inbox_attachments WHERE id = $1", attachment
    )
    assert status == "waiting"


async def test_ac_bulk_filing_refuses_a_flagged_attachment(firm: Firm) -> None:
    content = _form_1095c(2024)
    await _filed_before(firm, content)
    attachment = await firm.receive(firm.feld, "Feld_1095C_2024.pdf", content)

    bulk = await firm.post(
        "/v1/inbox/attachments/bulk-file",
        {"attachment_ids": [str(attachment)], "seen_proposals": []},
    )
    assert bulk.status_code == 200, bulk.text
    [result] = cast(list[dict[str, object]], bulk.json()["results"])
    assert (result["attachment_id"], result["outcome"]) == (str(attachment), "has_flags")
    assert await firm.decisions(attachment) == 0
    (row,) = await firm.net.seed.rows(
        "SELECT status, filed_evidence_version_id FROM inbox_attachments WHERE id = $1",
        attachment,
    )
    assert row["status"] == "waiting" and row["filed_evidence_version_id"] is None


async def test_ac_filing_to_another_clients_request_is_refused(firm: Firm) -> None:
    whitley = await firm.net.seed.site(firm.tenant, firm.grace.user_id, "Whitley")
    attachment = await firm.receive(firm.feld, "Feld_1095C_2025.pdf", _form_1095c(2025))
    message = await firm.message_of(attachment)
    versions_before = await firm.net.seed.value(
        "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", firm.tenant
    )

    filed = await firm.post(
        f"/v1/inbox/messages/{message}/triage/apply",
        {
            "decisions": [
                {
                    "attachment_id": str(attachment),
                    "decision": "file",
                    "destination": {"kind": "request", "id": str(whitley.item_id)},
                }
            ]
        },
    )
    assert filed.status_code in (404, 409), filed.text
    if filed.status_code == 409:
        assert filed.json()["detail"] == "destination_outside_client"
    assert await firm.decisions(attachment) == 0
    versions_after = await firm.net.seed.value(
        "SELECT count(*) FROM evidence_versions WHERE tenant_id = $1", firm.tenant
    )
    assert versions_after == versions_before
