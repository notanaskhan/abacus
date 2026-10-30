# ac-test-author: ayushkbhatia
"""N-01-T17 (TASK-2137; DEC-1177): rule classification and code flags on intake attachments.

Acceptance (the task row): "The 2024 1095-C is flagged wrong year and duplicate, and the Collins
W-2c forces Hold with 7713 vs 7731."

Boundary: the upload steps and `communications.attachment_classified` as the worker calls them;
outcomes through SQL (`document_classifications`, `inbox_attachment_flags`).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

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
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
EVIDENCE: Final = "n01t17-evidence"
MASTER: Final = b"n01t17-independent-master-key-0123456789"


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


async def _firm(net: Net) -> tuple[uuid.UUID, Person, Site]:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'inbox.firm_intake', 'true', 'test-seed', 'N-01-T17')",
        tenant,
    )
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Feld")
    # A TY2025 return: the year the client's work is for.
    await seed.run(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, period_start, "
        "period_end, created_by) VALUES ($1, $2, $3, 'tax_return', 'TY2025 Form 1040', "
        "'2025-01-01', '2025-12-31', $4)",
        tenant,
        site.engagement_id,
        site.client_id,
        admin.user_id,
    )
    return tenant, admin, site


async def _receive(
    net: Net, tenant: uuid.UUID, site: Site, file_name: str, content: bytes
) -> uuid.UUID:
    """One matched email with one file, run through the upload steps and the classify step."""
    system = TenantContext(tenant, "system", "test.n01t17")
    address = f"sender+{uuid.uuid4().hex[:6]}@example.com"
    await net.seed.run(
        "INSERT INTO inbox_sender_rules (tenant_id, address_hmac, address_sealed, client_id, "
        "created_by) SELECT $1, $2, '\\x00', $3, user_id FROM memberships "
        "WHERE tenant_id = $1 LIMIT 1",
        tenant,
        address_hash(address).hex(),
        site.client_id,
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
    given = UploadInput(str(tenant), INTAKE, str(got.attachment_id))
    await extract_upload(given)
    await words_upload(given)
    await pii_scan_upload(given)
    await attachment_classified(TriageInput(str(tenant), str(got.attachment_id)))
    return got.attachment_id


async def _flags(net: Net, attachment: uuid.UUID) -> dict[str, tuple[str, dict[str, object]]]:
    rows = await net.seed.rows(
        "SELECT kind, severity, facts FROM inbox_attachment_flags WHERE attachment_id = $1 "
        "AND run_no = (SELECT max(run_no) FROM inbox_attachment_flags WHERE attachment_id = $1)",
        attachment,
    )
    return {r["kind"]: (r["severity"], json.loads(r["facts"])) for r in rows}


async def test_ac_2025_1095c_classified_by_rule_with_no_flags(net: Net) -> None:
    tenant, _admin, site = await _firm(net)
    attachment = await _receive(net, tenant, site, "Feld_1095C_2025.pdf", _form_1095c(2025))
    (row,) = await net.seed.rows(
        "SELECT form_family, form_code, tax_year, page_count, proposed_by_kind, kind, "
        "rules_version, subject_kind FROM document_classifications WHERE subject_id = $1",
        attachment,
    )
    assert row["form_family"] == "1095-C" and row["tax_year"] == 2025
    assert row["page_count"] == 1 and row["proposed_by_kind"] == "rule"
    assert row["kind"] == "tax_form" and row["subject_kind"] == "inbox_attachment"
    assert await _flags(net, attachment) == {}
    linked = await net.seed.value(
        "SELECT classification_id FROM inbox_attachments WHERE id = $1", attachment
    )
    assert linked is not None


async def test_ac_2024_1095c_is_wrong_year_and_duplicate(net: Net) -> None:
    tenant, _admin, site = await _firm(net)
    content = _form_1095c(2024)
    # The same bytes were filed as a version on Mar 3, 2025 (a version of its own: versions are
    # immutable).
    fingerprint = hashlib.sha256(content).hexdigest()
    filed = await net.seed.value(
        "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, version_no, "
        "fingerprint, storage_key, storage_version_id, size_bytes, media_type, source, method) "
        "SELECT tenant_id, engagement_id, evidence_item_id, 2, $2, $3, 'v1', $4, "
        "'application/pdf', 'upload', 'uploaded' FROM evidence_versions WHERE id = $1 "
        "RETURNING id",
        site.version_id,
        fingerprint,
        f"tenants/{tenant}/sha256/{fingerprint}",
        len(content),
    )
    attachment = await _receive(net, tenant, site, "Feld_1095C_2024.pdf", content)
    flags = await _flags(net, attachment)
    assert flags["wrong_year"] == ("block_bulk", {"tax_year": 2024, "expected_year": 2025})
    severity, facts = flags["duplicate_hash"]
    assert severity == "block_bulk"
    assert facts["duplicate_of_version"] == str(filed)


async def test_ac_collins_w2c_forces_hold_7713_vs_7731(net: Net) -> None:
    tenant, _admin, site = await _firm(net)
    await net.seed.run(
        "UPDATE client_entities SET tin_sealed = '\\x00', tin_last4 = '7731', tin_kind = 'ssn', "
        "tin_status = 'on_file', tin_fingerprint = $2 WHERE id = $1",
        site.entity_id,
        hashlib.sha256(b"collins").digest(),
    )
    attachment = await _receive(net, tenant, site, "Collins_W-2c_2025.pdf", W2C)
    flags = await _flags(net, attachment)
    assert flags["tin_mismatch"] == (
        "force_hold",
        {"detected_last4": "7713", "record_last4": ["7731"]},
    )
    assert flags["corrected_form"][0] == "info"
    (code,) = await net.seed.rows(
        "SELECT form_code, corrected, taxpayer_tin_last4 FROM document_classifications "
        "WHERE subject_id = $1",
        attachment,
    )
    assert code["form_code"] == "W-2c" and code["corrected"] is True
    assert code["taxpayer_tin_last4"] == "7713"


async def test_classifications_are_insert_only(net: Net) -> None:
    tenant, _admin, site = await _firm(net)
    attachment = await _receive(net, tenant, site, "Feld_1095C_2025.pdf", _form_1095c(2025))
    # A second run is a new classification and a new flag run, never an edit.
    await attachment_classified(TriageInput(str(tenant), str(attachment)))
    count = await net.seed.value(
        "SELECT count(*) FROM document_classifications WHERE subject_id = $1", attachment
    )
    assert count == 2
    with pytest.raises(Exception, match="insert-only"):
        await net.seed.run(
            "UPDATE document_classifications SET tax_year = 2024 WHERE subject_id = $1",
            attachment,
        )
