"""N-02-T38 (TASK-2519; N-02 §3.3, §3.13; I-RETENTION-FLOOR; DEC-1567) against the database, the
records bucket and the fake provider: "A tampered records object fails the nightly check with an
alarm, and an 8879 package's retain-until only ever moves forward."

The envelope is N-02-T14's two-signer Form 8879, completed by the workflow's activities. Also:
the legible evidence page is stored with the package and carried by Download evidence (or its
absence is recorded when the renderer cannot run), a §7216 consent's package takes the
`consent_evidence` record type, and an accepted federal acknowledgement extends the 8879 to the
IRS received date plus three years.
"""

from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import records, storage
from abacus.modules.signatures import activities, integrity
from abacus.modules.signatures.api import (
    RetentionNotExtended,
    configure_provider,
    extend_retention,
    register_reminder_sender,
)
from abacus.modules.tax.engine_files import kept_until
from abacus_tools.fakes.esign import FakeEsign

from . import test_n02t14_envelope_workflow as t14
from .support import Net

if TYPE_CHECKING:
    from collections.abc import Iterator

    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
IP = t14.IP
EVIDENCE = "n02t38-evidence"
RECORDS = "n02t38-records"
Sent = t14.Sent


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


@pytest.fixture
def fake(raw: S3Client) -> Iterator[FakeEsign]:
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(b"n02t38-hardening-master-key-0123456789"))
    storage.configure_storage(raw, EVIDENCE)
    records.configure_records(raw, RECORDS)
    provider = FakeEsign()
    configure_provider(provider)
    yield provider
    configure_provider(None)
    register_reminder_sender(None)
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    forget_flags()


PAGE = b"%PDF-1.7\n% the legible evidence page (stub)\n"


async def _completed(net: Net, fake: FakeEsign) -> t14.Sent:
    sent = await t14.sent_8879(net)  # N-02-T14's two-signer Form 8879
    assert (await activities.envelope_send(sent.given)).status == "sent"
    pid = cast(
        str,
        await net.seed.value(
            "SELECT provider_envelope_id FROM envelopes WHERE id = $1", sent.envelope_id
        ),
    )
    for signer in sent.signers:
        fake.sign(pid, str(signer), ip=IP)
    assert await activities.envelope_poll(sent.given) == "completed"
    assert await activities.envelope_complete(sent.given) == "recorded"
    return sent


@pytest.fixture
def page(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    """The renderer's isolated child is image-bound (WeasyPrint): a fixed page stands in."""
    asked: list[object] = []

    def legible(title: str, signers: object, documents: object, at: datetime) -> bytes:
        asked.append((title, signers, documents))
        return PAGE

    monkeypatch.setattr(integrity, "legible_page", legible)
    return asked


async def test_ac_a_tampered_record_fails_the_nightly_check_with_an_alarm(
    net: Net, fake: FakeEsign, raw: S3Client, monkeypatch: pytest.MonkeyPatch, page: list[object]
) -> None:
    sent = await _completed(net, fake)
    alarms: list[int] = []

    def add(n: int, *_args: object, **_kwargs: object) -> None:
        alarms.append(n)

    monkeypatch.setattr(integrity._failures, "add", add)  # pyright: ignore[reportPrivateUsage] -- the alarm's counter
    assert await integrity.verify_firm(sent.tenant_id) == []
    key = cast(
        str,
        await net.seed.value(
            "SELECT package_key FROM signature_evidence WHERE envelope_id = $1 LIMIT 1",
            sent.envelope_id,
        ),
    )
    raw.put_object(Bucket=RECORDS, Key=key, Body=b'{"tampered": true}')  # a newer version
    assert await integrity.verify_firm(sent.tenant_id) == [sent.envelope_id]
    assert await integrity.verify_firm(sent.tenant_id) == [sent.envelope_id]
    assert alarms == [1, 1]  # every run that finds it pages
    flagged = await net.seed.value(
        "SELECT count(*) FROM envelope_events WHERE envelope_id = $1 "
        "AND kind = 'envelope.integrity_failed'",
        sent.envelope_id,
    )
    assert flagged == 1  # the drawer's flag is recorded once


async def test_ac_an_8879_packages_retain_until_only_moves_forward(
    net: Net, fake: FakeEsign, page: list[object]
) -> None:
    sent = await _completed(net, fake)
    system = TenantContext(sent.tenant_id, "system", "tax:efile_retention")
    held = cast(
        date,
        await net.seed.value(
            "SELECT max(retain_until) FROM signature_evidence WHERE envelope_id = $1",
            sent.envelope_id,
        ),
    )
    with pytest.raises(RetentionNotExtended):
        await extend_retention(system, sent.envelope_id, held - timedelta(days=1))
    later = held + timedelta(days=400)
    assert await extend_retention(system, sent.envelope_id, later) == later
    with pytest.raises(RetentionNotExtended):
        await extend_retention(system, sent.envelope_id, held)
    kept = await net.seed.value(
        "SELECT retain_until FROM envelopes WHERE id = $1", sent.envelope_id
    )
    assert kept == later


def test_the_acknowledgement_extends_to_the_received_date_plus_three_years() -> None:
    assert kept_until("2026-09-18T14:02:00-05:00") == date(2029, 9, 18)
    assert kept_until("2028-02-29") == date(2031, 3, 1)
    assert kept_until("not a date") is None


async def test_the_legible_page_is_stored_and_downloaded(
    net: Net, fake: FakeEsign, raw: S3Client, page: list[object]
) -> None:
    sent = await _completed(net, fake)
    assert len(page) == 1
    _title, signers, _documents = cast(tuple[str, list[dict[str, str]], list[str]], page[0])
    assert [s["ip_masked"] for s in signers] == ["203.0.•••.•••", "203.0.•••.•••"]
    assert all(IP not in str(s) for s in signers)
    hashes = await net.seed.rows(
        "SELECT document_sha256s FROM signature_evidence WHERE envelope_id = $1",
        sent.envelope_id,
    )
    digest = hashlib.sha256(PAGE).hexdigest()
    assert all(digest in list(r["document_sha256s"]) for r in hashes)
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'signatures.envelopes', 'true', 'n02t38', 'N-02-T38')",
        sent.tenant_id,
    )
    downloaded = await net.call(
        "GET", f"/v1/envelopes/{sent.envelope_id}/evidence.zip", sent.grace
    )
    assert downloaded.status_code == 200, downloaded.text
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        names = archive.namelist()
        assert f"documents/{digest}" in names and "manifest.sha256" in names
        assert archive.read(f"documents/{digest}") == PAGE
        assert f"documents/{digest}" in archive.read("manifest.sha256").decode()


async def test_a_missing_page_is_recorded_never_blocking(
    net: Net, fake: FakeEsign, monkeypatch: pytest.MonkeyPatch
) -> None:
    def none(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(integrity, "legible_page", none)
    sent = await _completed(net, fake)
    failed = await net.seed.value(
        "SELECT count(*) FROM envelope_events WHERE envelope_id = $1 "
        "AND kind = 'envelope.legible_copy_failed'",
        sent.envelope_id,
    )
    assert failed == 1


async def test_a_consent_package_takes_the_consent_record_type(
    net: Net, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[str] = []

    async def retain(tenant: object, record_type: str, line: str, at: datetime) -> datetime:
        asked.append(record_type)
        return at + timedelta(days=365 * 3)

    monkeypatch.setattr(integrity, "retain_until_for", retain)
    tenant = TenantContext(uuid.uuid4(), "system", "probe")
    now = datetime.now(UTC)
    await integrity.retain_until(tenant, "consent_7216", "tax", now)
    await integrity.retain_until(tenant, "form_8879", "tax", now)
    assert asked == ["consent_evidence", "signature_evidence"]
