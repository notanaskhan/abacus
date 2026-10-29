# ac-test-author: ayushkbhatia
"""N-02-T14 (TASK-2015; N-02 §3.3, §3.5, §3.7; ADR-149; DEC-74): EnvelopeWorkflow's activities
on the fake provider.

Acceptance (the task row): "A fake two-signer envelope completes under replay with both packages
hashed in COMPLIANCE storage and one envelope.completed." The replay half is
`tests/workflows/test_envelope_replay.py`; this drives the activities in the workflow's order
against the database, the records bucket and the fake provider.

Also: the send is idempotent; a poll moves the envelope forward only; each package carries the
five IRS items and never the full address; a retried completion records nothing twice; a
reminder with no registered template sender is skipped, and the policy cap stops them; an open
envelope past its expiry is Expired and voided at the provider.

Boundary: the activity functions called as the worker calls them; outcomes through SQL and S3.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Final, cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import records, storage
from abacus.modules.signatures import activities
from abacus.modules.signatures.api import (
    EnvelopeInput,
    ReminderDue,
    configure_provider,
    register_reminder_sender,
)
from abacus.modules.signatures.reminders import reminder_instants
from abacus_tools.fakes.esign import FakeEsign

from .support import Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
EVIDENCE: Final = "n02t14-evidence"
RECORDS: Final = "n02t14-records"
MASTER: Final = b"n02t14-independent-master-key-0123456789"
IP: Final = "203.0.113.42"


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
    configure_key_service(LocalKeyService(MASTER))
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


@dataclass(frozen=True)
class Sent:
    net: Net
    tenant_id: uuid.UUID
    grace: Person
    site: Site
    envelope_id: uuid.UUID
    signers: tuple[uuid.UUID, uuid.UUID]

    @property
    def given(self) -> EnvelopeInput:
        return EnvelopeInput(str(self.tenant_id), str(self.envelope_id))


async def _sent(net: Net, *, expires_in: timedelta = timedelta(days=20)) -> Sent:
    """A two-signer Form 8879 Grace sent, as the human send leaves it (N-02-T22)."""
    seed = net.seed
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Kowal")
    await seed.member(site, grace, "manager")
    await seed.run(
        "WITH t AS (SELECT set_config('app.tenant_id', $1::text, true)) "
        "INSERT INTO retention_policies (tenant_id, record_type, service_line, firm_years, "
        "clock_start_event, updated_by) SELECT $1::uuid, 'signature_evidence', 'any', 7, "
        "'event_date', 'test-seed' FROM t",
        str(tenant),
    )
    envelope = uuid.uuid4()
    signers = (uuid.uuid4(), uuid.uuid4())
    now = datetime.now(UTC)
    statements: list[tuple[str, tuple[object, ...]]] = [
        (
            "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, client_id, "
            "engagement_id, title, provider, status, drafted_by_kind, drafted_by, sent_by, "
            "sent_at, expires_at, reminder_cadence) VALUES ($1, $2, 1, 'form_8879', "
            "'efile_authorization', $3, $4, 'TY2025 Form 8879', 'fake', 'sent', 'human', $5, "
            "$5, $6, $7, 'daily')",
            (
                envelope,
                tenant,
                site.client_id,
                site.engagement_id,
                grace.user_id,
                now,
                now + expires_in,
            ),
        ),
        (
            'INSERT INTO envelope_documents (tenant_id, envelope_id, "order", '
            "evidence_version_id, sha256) VALUES ($1, $2, 1, $3, $4)",
            (tenant, envelope, site.version_id, "a" * 64),
        ),
    ]
    for order, signer in enumerate(signers, start=1):
        contact = await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, $3, 'client_person') RETURNING id",
            tenant,
            site.client_id,
            f"Kowal signer {order}",
        )
        statements.append(
            (
                'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", party_kind, '
                "contact_id, identity_method) VALUES ($1, $2, $3, $4, 'contact', $5, 'kba')",
                (signer, tenant, envelope, order, contact),
            )
        )
    await seed.run_untriggered_many(statements)
    return Sent(net, tenant, grace, site, envelope, signers)


async def _provider_id(sent: Sent) -> str:
    return cast(
        str,
        await sent.net.seed.value(
            "SELECT provider_envelope_id FROM envelopes WHERE id = $1", sent.envelope_id
        ),
    )


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_a_fake_two_signer_envelope_completes_with_both_packages_in_compliance(
    net: Net, fake: FakeEsign, raw: S3Client
) -> None:
    sent = await _sent(net)
    plan = await activities.envelope_send(sent.given)
    assert plan.status == "sent"
    assert plan.reminders  # "daily", under the cap
    again = await activities.envelope_send(sent.given)
    assert again.status == "sent"
    assert fake.calls.count("create_and_send") == 1  # the second send found the envelope
    pid = await _provider_id(sent)

    fake.sign(pid, str(sent.signers[0]), ip=IP)
    assert await activities.envelope_poll(sent.given) == "partially_signed"
    fake.sign(pid, str(sent.signers[1]), ip=IP)
    assert await activities.envelope_poll(sent.given) == "completed"
    assert await activities.envelope_complete(sent.given) == "recorded"
    assert await activities.envelope_complete(sent.given) == "recorded"  # a retry adds nothing

    seed = net.seed
    rows = await seed.rows(
        "SELECT package_key, package_sha256, ip_masked, identity_result, signature_method, "
        "signed_image_key, login_ref, ip_sealed FROM signature_evidence WHERE envelope_id = $1",
        sent.envelope_id,
    )
    assert len(rows) == 2
    for row in rows:
        retention = raw.get_object_retention(Bucket=RECORDS, Key=row["package_key"])
        assert retention["Retention"].get("Mode") == "COMPLIANCE"
        body = raw.get_object(Bucket=RECORDS, Key=row["package_key"])["Body"].read()
        package = json.loads(body)
        # The five IRS items: image, date and time, address (masked; sealed) and login, result,
        # method.
        assert package["signed_image_sha256"] and package["signed_at"]
        assert package["ip_masked"] == "203.0.•••.•••" and package["login_ref"]
        assert package["identity_result"] and package["signature_method"] == "typed"
        assert IP not in body.decode()
        assert row["ip_sealed"] is not None
    completed = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'envelope.completed'",
        sent.tenant_id,
    )
    assert completed == 1
    filed = await seed.value(
        "SELECT count(*) FROM evidence_items WHERE tenant_id = $1 "
        "AND folder_kind = 'signed_authorizations'",
        sent.tenant_id,
    )
    assert filed == 1


async def test_a_reminder_needs_a_template_sender_and_stops_at_the_cap(
    net: Net, fake: FakeEsign
) -> None:
    sent = await _sent(net)
    await activities.envelope_send(sent.given)
    due = ReminderDue(str(sent.tenant_id), str(sent.envelope_id), 1)
    assert await activities.envelope_remind(due) == "skipped"
    asked: list[uuid.UUID] = []

    async def sender(_t: TenantContext, _e: uuid.UUID, signer: uuid.UUID, _n: int) -> bool:
        asked.append(signer)
        return True

    register_reminder_sender(sender)
    outcomes = [await activities.envelope_remind(due) for _ in range(4)]
    assert outcomes == ["sent", "sent", "sent", "capped"]  # no policy row: the default cap, 3
    assert set(asked) == set(sent.signers)


def test_reminders_fall_on_weekdays_at_nine_in_the_zone_and_before_expiry() -> None:
    friday = datetime(2026, 10, 30, 15, 0, tzinfo=UTC)
    out = reminder_instants(
        cadence="daily",
        sent_at=friday,
        expires_at=friday + timedelta(days=4),
        cap=3,
        zone="America/Chicago",
    )
    assert [r.isoformat() for r in out] == [
        "2026-11-02T15:00:00+00:00",  # Monday 9:00 CST, after the weekend
        "2026-11-03T15:00:00+00:00",
    ]
    assert (
        reminder_instants(
            cadence="hourly",
            sent_at=friday,
            expires_at=friday + timedelta(days=9),
            cap=3,
            zone="UTC",
        )
        == []
    )


async def test_an_open_envelope_past_its_expiry_is_expired_and_voided(
    net: Net, fake: FakeEsign
) -> None:
    sent = await _sent(net, expires_in=timedelta(seconds=-1))
    await activities.envelope_send(sent.given)
    assert await activities.envelope_expire(sent.given) == "expired"
    assert "void:expired" in fake.calls
    status = await net.seed.value("SELECT status FROM envelopes WHERE id = $1", sent.envelope_id)
    assert status == "expired"
    assert await activities.envelope_poll(sent.given) == "expired"  # a final status stays
