"""N-02-T27 (TASK-2421; N-02 §3.7; DF-11; Pub 1345; DEC-1469): the e-file authorization policy and
the handwritten fallback, on the fake provider.

Acceptance (the task row): "Irene Kowal's third failure closes Irene's remote path with no retry,
and Grace's upload of the hand-signed 8879 completes E2 with method Handwritten."

Also: each failure is counted once, as an event; the signer stays closed whatever the provider
says next; the sender is told (C16); the policy reads the floor and refuses a looser change; a
firm's stricter limit closes the signer sooner; the agent cannot record a hand-signed form, and
the database refuses one recorded by anyone but the person named.

E2 is N-02-T14's two-signer Form 8879 (`_sent`, shared rather than copied).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING, Final

import asyncpg
import pytest
from tests.integration.agent_tests.support import Seeder as AgentSeeder
from tests.integration.conftest import MigratedDatabase

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import records, storage
from abacus.modules.signatures import activities
from abacus.modules.signatures.api import configure_provider
from abacus_tools.fakes.esign import FakeEsign, FakeEsignError

from .support import Net
from .test_n02t14_envelope_workflow import Sent, provider_id, sent_8879

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client


pytestmark = pytest.mark.asyncio
EVIDENCE: Final = "n02t27-evidence"
RECORDS: Final = "n02t27-records"
MASTER: Final = b"n02t27-independent-master-key-0123456789"
SCAN: Final = b"%PDF-1.7\n% Form 8879, signed by hand by Irene Kowal\n%%EOF\n"


@pytest.fixture(scope="module")
def raw(s3_settings: dict[str, str]) -> Iterator[S3Client]:
    """This suite's own buckets (T-02-T14's module makes its own)."""
    client = s3_client(
        endpoint_url=s3_settings["endpoint_url"],
        access_key=s3_settings["access_key"],
        secret_key=s3_settings["secret_key"],
        region=s3_settings["region"],
    )
    for bucket in (EVIDENCE, RECORDS):
        with contextlib.suppress(client.exceptions.BucketAlreadyOwnedByYou):
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
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    forget_flags()


async def _out(net: Net, fake: FakeEsign) -> tuple[Sent, str]:
    sent = await sent_8879(net)
    await net.seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, 'signatures.envelopes', 'true', 'test-seed', 'N-02-T27')",
        sent.tenant_id,
    )
    await activities.envelope_send(sent.given)
    return sent, await provider_id(sent)


async def _irene(sent: Sent) -> dict[str, object]:
    rows = await sent.net.seed.rows(
        "SELECT status, kba_failures, signature_method, wet_recorded_by FROM envelope_signers "
        "WHERE id = $1",
        sent.signers[1],
    )
    return dict(rows[0])


async def _wet(sent: Sent, who_headers: dict[str, str], attempt: str) -> int:
    staged = await sent.net.http.post(
        "/v1/envelopes/import/files",
        params={
            "filename": "kowal-8879-irene.pdf",
            "client_id": str(sent.site.client_id),
            "engagement_id": str(sent.site.engagement_id),
        },
        content=SCAN,
        headers={**who_headers, "Content-Type": "application/octet-stream"},
    )
    assert staged.status_code == 201, staged.text
    recorded = await sent.net.http.post(
        f"/v1/envelopes/{sent.envelope_id}/signers/{sent.signers[1]}/wet-signature",
        json={
            "upload_id": staged.json()["id"],
            "signed_on": "2026-09-11",
            "attested": True,
            "received_on": "2026-09-12",
        },
        headers={**who_headers, "Idempotency-Key": attempt},
    )
    return recorded.status_code


async def test_ac1_irenes_third_failure_closes_her_path_and_graces_upload_completes_e2(
    net: Net, fake: FakeEsign
) -> None:
    sent, pid = await _out(net, fake)
    seed = net.seed

    fake.sign(pid, str(sent.signers[0]), ip="203.0.113.42")  # Thomas signs remotely
    for n in (1, 2):
        fake.fail_identity(pid, str(sent.signers[1]))
        await activities.envelope_poll(sent.given)
        irene = await _irene(sent)
        assert irene["kba_failures"] == n and irene["status"] != "verification_failed"
    fake.fail_identity(pid, str(sent.signers[1]))
    await activities.envelope_poll(sent.given)
    await activities.envelope_poll(sent.given)  # a second poll records nothing twice
    irene = await _irene(sent)
    assert (irene["status"], irene["kba_failures"]) == ("verification_failed", 3)
    failures = await seed.value(
        "SELECT count(*) FROM envelope_events WHERE envelope_id = $1 AND signer_id = $2 "
        "AND kind = 'signer.kba_failed'",
        sent.envelope_id,
        sent.signers[1],
    )
    assert failures == 3
    told = await seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'envelope.signer_verification_failed'",
        sent.tenant_id,
    )
    assert len(told) == 1
    with pytest.raises(FakeEsignError):  # no retry: the provider refuses, and so do we
        fake.sign(pid, str(sent.signers[1]))
    sessions = await seed.value(
        "SELECT count(*) FROM signing_sessions WHERE signer_id = $1 AND state = 'issued'",
        sent.signers[1],
    )
    assert sessions == 0

    # Grace uploads Irene's hand-signed 8879: Irene signed, method Handwritten; E2 completes.
    assert await _wet(sent, net.headers(sent.grace), "wet-signature-1") == 200
    irene = await _irene(sent)
    assert (irene["status"], irene["signature_method"], irene["wet_recorded_by"]) == (
        "signed",
        "handwritten",
        sent.grace.user_id,
    )
    assert await seed.value("SELECT status FROM envelopes WHERE id = $1", sent.envelope_id) == (
        "completed"
    )
    assert await activities.envelope_poll(sent.given) == "completed"
    assert await activities.envelope_complete(sent.given) == "recorded"
    evidence = await seed.rows(
        "SELECT signer_id, signature_method FROM signature_evidence WHERE envelope_id = $1 "
        "ORDER BY signature_method",
        sent.envelope_id,
    )
    assert sorted((r["signer_id"], r["signature_method"]) for r in evidence) == sorted(
        [(sent.signers[1], "handwritten"), (sent.signers[0], "typed")]
    )
    completed = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'envelope.completed'",
        sent.tenant_id,
    )
    assert completed == 1


async def test_ac1_only_a_closed_signer_signs_on_paper_and_only_a_person_records_it(
    net: Net, fake: FakeEsign, migrated_db: MigratedDatabase
) -> None:
    sent, pid = await _out(net, fake)
    # Irene's remote path is open: no paper form yet.
    assert await _wet(sent, net.headers(sent.grace), "wet-signature-early") == 409
    for _ in range(3):
        fake.fail_identity(pid, str(sent.signers[1]))
    await activities.envelope_poll(sent.given)
    # The database: a hand-signed form named for Grace, written by a system actor, is refused.
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await AgentSeeder(migrated_db.superuser_dsn).as_actor(
            sent.tenant_id,
            ("system", "test"),
            "UPDATE envelope_signers SET status = 'signed', signed_at = now(), "
            "signature_method = 'handwritten', wet_recorded_by = $1 WHERE id = $2",
            sent.grace.user_id,
            sent.signers[1],
        )


async def test_ac1_the_policy_reads_the_floor_and_only_tightens(net: Net, fake: FakeEsign) -> None:
    sent, pid = await _out(net, fake)
    security = await net.seed.person(sent.tenant_id, "security_admin")
    listed = await net.call("GET", "/v1/envelope-policies", sent.grace)
    assert listed.status_code == 200, listed.text
    efile = next(p for p in listed.json() if p["policy_family"] == "efile_authorization")
    assert (efile["kba_max_attempts"], efile["failure_path"], efile["version"]) == (
        3,
        "wet_signature",
        0,
    )
    assert "kba" in efile["allowed_identity_methods"]
    assert "email_code" not in efile["allowed_identity_methods"]

    looser = {
        "allowed_identity_methods": ["kba", "email_code"],
        "default_identity_method": "kba",
        "kba_max_attempts": 3,
        "max_reminders": 3,
        "default_expiry_days": 30,
        "countersign_required": False,
        "version": 0,
    }
    refused = await net.call(
        "PUT", "/v1/envelope-policies/efile_authorization", security, body=looser
    )
    assert (refused.status_code, refused.json()["detail"]) == (409, "policy_not_stricter")
    stricter = {
        **looser,
        "allowed_identity_methods": ["kba", "in_person_id"],
        "kba_max_attempts": 2,
    }
    saved = await net.call(
        "PUT", "/v1/envelope-policies/efile_authorization", security, body=stricter
    )
    assert saved.status_code == 200, saved.text
    assert (saved.json()["kba_max_attempts"], saved.json()["version"]) == (2, 1)
    denied = await net.call(
        "PUT",
        "/v1/envelope-policies/efile_authorization",
        sent.grace,
        body={**stricter, "version": 1},
    )
    assert denied.status_code == 403

    # The firm's limit of two closes Irene at her second failure.
    fake.fail_identity(pid, str(sent.signers[1]))
    fake.fail_identity(pid, str(sent.signers[1]))
    await activities.envelope_poll(sent.given)
    irene = await _irene(sent)
    assert (irene["status"], irene["kba_failures"]) == ("verification_failed", 2)
