# ac-test-author: ayushkbhatia
"""N-02-T08 (TASK-1728; N-02 §3.1; SIG-01 r; DEC-818): record-mode import.

Acceptance (the task row): "Importing Copperleaf's signed 2026 Close letter stores both files
write-once with hashes, files the copy and emits one envelope.completed naming the importer."

Also: a replay of the same `Idempotency-Key` answers the same envelope; the scanner refuses an
infected file and nothing is stored; another person's staged file cannot be imported; no
retention floor means no import; the flag off answers 404.

Boundary: `create_app()` over HTTP as each signed-in person; outcomes through SQL and the
records bucket.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, cast

import httpx
import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.scanning import inject_verdict
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import records, storage

from .support import Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]
FLAG: Final = "signatures.envelopes"
EVIDENCE: Final = "n02t08-evidence"
RECORDS: Final = "n02t08-records"
MASTER: Final = b"n02t08-independent-master-key-0123456789"
LETTER: Final = b"%PDF-1.7\n% Copperleaf 2026 Close engagement letter, signed\n%%EOF\n"
CERTIFICATE: Final = b"%PDF-1.7\n% Certificate of completion\n%%EOF\n"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    for bucket in (EVIDENCE, RECORDS):
        client.create_bucket(Bucket=bucket, ObjectLockEnabledForBucket=True)
    yield client


@pytest.fixture(autouse=True)
def wired(raw: S3Client) -> Iterator[None]:
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    records.configure_records(raw, RECORDS)
    yield
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    forget_flags()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    grace: Person  # Firm Admin and manager on the engagement: imports
    other: Person  # another Firm Admin and manager
    site: Site
    contact_id: uuid.UUID

    async def stage(self, who: Person, content: bytes, name: str) -> httpx.Response:
        return await self.net.http.post(
            "/v1/envelopes/import/files",
            params={"filename": name},
            content=content,
            headers={**self.net.headers(who), "Content-Type": "application/octet-stream"},
        )

    async def import_(self, who: Person, body: Body, key: str = "import-1") -> httpx.Response:
        return await self.net.http.post(
            "/v1/envelopes/import",
            json=body,
            headers={**self.net.headers(who), "Idempotency-Key": key},
        )


async def _floor(firm: Firm) -> None:
    await firm.net.seed.run(
        "INSERT INTO retention_policies (tenant_id, record_type, service_line, firm_years, "
        "clock_start_event, updated_by) VALUES ($1, 'signature_evidence', 'any', 7, "
        "'event_date', 'test-seed')",
        firm.tenant_id,
    )


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'N-02-T08')",
        tenant,
        FLAG,
    )
    admin = await seed.person(tenant, "firm_admin")
    # SIG-01's importer is a Firm Admin (client_service at the firm, DEC-20); staging a file is
    # authorised at the firm, the import on the engagement she is also a manager of.
    grace = await seed.person(tenant, "firm_admin")
    other = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Copperleaf")
    await seed.member(site, grace, "manager")
    await seed.member(site, other, "manager")
    contact = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, 'Copperleaf signer', 'client_person') RETURNING id",
            tenant,
            site.client_id,
        ),
    )
    made = Firm(net, tenant, grace, other, site, contact)
    await _floor(made)
    return made


def _body(firm: Firm, uploads: list[str]) -> Body:
    return {
        "purpose": "engagement_letter",
        "client_id": str(firm.site.client_id),
        "engagement_id": str(firm.site.engagement_id),
        "title": "2026 Close engagement letter",
        "provider_name": "DocuSign",
        "signers": [
            {"contact_id": str(firm.contact_id), "signed_on": "2026-04-02"}
            | {"identity_method": "email_code"},
            {"user_id": str(firm.grace.user_id), "role": "countersigner"}
            | {"signed_on": "2026-04-03", "identity_method": "firm_sso"},
        ],
        "upload_ids": uploads,
        "attested": True,
    }


async def _staged(firm: Firm, who: Person | None = None) -> list[str]:
    ids: list[str] = []
    for content, name in ((LETTER, "letter.pdf"), (CERTIFICATE, "certificate.pdf")):
        response = await firm.stage(who or firm.grace, content, name)
        assert response.status_code == 201, response.text
        ids.append(cast(Body, response.json())["id"])
    return ids


def _records(raw: S3Client, tenant: uuid.UUID) -> dict[str, str]:
    """Each stored record's key and its Object Lock mode."""
    listed = raw.list_objects_v2(Bucket=RECORDS, Prefix=f"records/{tenant}/signature_evidence/")
    out: dict[str, str] = {}
    for item in listed.get("Contents", []):
        key = item.get("Key", "")
        retention = raw.get_object_retention(Bucket=RECORDS, Key=key)["Retention"]
        out[key] = str(retention.get("Mode"))
    return out


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_copperleafs_signed_letter_is_stored_filed_and_completed(
    firm: Firm, raw: S3Client
) -> None:
    response = await firm.import_(firm.grace, _body(firm, await _staged(firm)))
    assert response.status_code == 201, response.text
    made = cast(Body, response.json())
    envelope = uuid.UUID(made["row"]["id"])
    assert made["row"]["status"] == "completed"
    assert made["row"]["provider"] == "record"
    assert (made["row"]["signed"], made["row"]["total"]) == (2, 2)

    # Both files write-once with hashes, and the manifest, in COMPLIANCE mode.
    stored = _records(raw, firm.tenant_id)
    for content in (LETTER, CERTIFICATE):
        key = f"records/{firm.tenant_id}/signature_evidence/{hashlib.sha256(content).hexdigest()}"
        assert stored.get(key) == "COMPLIANCE"
    assert len(stored) == 3
    seed = firm.net.seed
    package = await seed.value(
        "SELECT DISTINCT package_sha256 FROM signature_evidence WHERE envelope_id = $1", envelope
    )
    assert f"records/{firm.tenant_id}/signature_evidence/{package}" in stored
    hashes = await seed.value(
        "SELECT document_sha256s FROM signature_evidence WHERE envelope_id = $1 LIMIT 1", envelope
    )
    assert list(cast(list[str], hashes)) == [
        hashlib.sha256(LETTER).hexdigest(),
        hashlib.sha256(CERTIFICATE).hexdigest(),
    ]

    # The signed copy filed under Signed authorizations.
    folder = await seed.value(
        "SELECT i.folder_kind FROM envelope_documents d "
        "JOIN evidence_versions v ON v.id = d.evidence_version_id "
        "JOIN evidence_items i ON i.id = v.evidence_item_id WHERE d.envelope_id = $1",
        envelope,
    )
    assert folder == "signed_authorizations"

    # One envelope.completed naming the importer, and the audit envelope.imported.
    events = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = 'envelope.completed'",
        firm.tenant_id,
    )
    assert len(events) == 1
    assert str(firm.grace.user_id) in str(events[0]["payload"])
    actor = await seed.value(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 AND action = 'envelope.imported'",
        firm.tenant_id,
    )
    assert actor == str(firm.grace.user_id)


# --- The rest of the row ------------------------------------------------------------------------


async def test_a_replay_answers_the_same_envelope(firm: Firm) -> None:
    body = _body(firm, await _staged(firm))
    first = await firm.import_(firm.grace, body)
    again = await firm.import_(firm.grace, body)
    assert first.status_code == again.status_code == 201
    assert first.json()["row"]["id"] == again.json()["row"]["id"]
    count = await firm.net.seed.value(
        "SELECT count(*) FROM envelopes WHERE tenant_id = $1", firm.tenant_id
    )
    assert count == 1


async def test_an_infected_file_is_refused_and_nothing_is_stored(firm: Firm) -> None:
    bad = b"%PDF-1.7\n% infected\n%%EOF\n"
    inject_verdict(hashlib.sha256(bad).hexdigest(), "infected")
    response = await firm.stage(firm.grace, bad, "letter.pdf")
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "file_refused"
    count = await firm.net.seed.value(
        "SELECT count(*) FROM envelope_import_files WHERE tenant_id = $1", firm.tenant_id
    )
    assert count == 0


async def test_another_persons_staged_file_cannot_be_imported(firm: Firm) -> None:
    response = await firm.import_(firm.grace, _body(firm, await _staged(firm, firm.other)))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "import_file_unavailable"


async def test_a_file_is_consumed_by_one_import_only(firm: Firm) -> None:
    uploads = await _staged(firm)
    assert (await firm.import_(firm.grace, _body(firm, uploads))).status_code == 201
    again = await firm.import_(firm.grace, _body(firm, uploads), key="import-2")
    assert again.status_code == 409
    assert again.json()["detail"]["code"] == "import_file_unavailable"


async def test_no_retention_floor_means_no_import(firm: Firm, raw: S3Client) -> None:
    await firm.net.seed.run("DELETE FROM retention_policies WHERE tenant_id = $1", firm.tenant_id)
    response = await firm.import_(firm.grace, _body(firm, await _staged(firm)))
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "retention_floor_missing"
    assert _records(raw, firm.tenant_id) == {}


async def test_the_flag_off_answers_404(firm: Firm) -> None:
    uploads = await _staged(firm)
    await firm.net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        firm.tenant_id,
        FLAG,
    )
    forget_flags()
    response = await firm.import_(firm.grace, _body(firm, uploads))
    assert response.status_code == 404
