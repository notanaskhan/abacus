# ac-test-author: ayushkbhatia
"""N-02-T25 (TASK-2233; N-02 §4.4 v1.1; DEC-85; DEC-1285): C7 v1.1 for T-01 and T-02 against the
database and the records bucket.

Acceptance (the task row): "The T-01, T-02 and F-06 consumer suites pass in N-02's CI and a
shortening extend_retention call is refused." The consumer suites are the C7 contract tests under
`tests/contracts/c7_n02/`; this proves the database half: a shortening call is refused (409 here,
and 0432's trigger beneath it), an extension locks every stored record further, the superseded
marker is the system's alone and permanent and leaves every gate unmet, TAX-01's chips come per
work item, and the poll emits the signer-level events.

Boundary: `signatures.api` called as T-01 and T-02 would; the activities as the worker runs them;
outcomes through SQL and the records bucket's object-lock headers.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Final, cast

import asyncpg
import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import records, storage
from abacus.modules.identity.api import AuthContext
from abacus.modules.signatures import activities
from abacus.modules.signatures.api import (
    EFILE_GATE,
    TAX_RETURN,
    EnvelopeInput,
    RetentionNotExtended,
    SystemOnly,
    configure_provider,
    envelope_gate_facts,
    envelope_summaries_for,
    extend_retention,
    supersede_for_amount_change,
)
from abacus_tools.fakes.esign import FakeEsign

from .support import Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
EVIDENCE: Final = "n02t25-evidence"
RECORDS: Final = "n02t25-records"
MASTER: Final = b"n02t25-independent-master-key-0123456789"


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
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    forget_flags()


@dataclass(frozen=True)
class Signed:
    net: Net
    tenant: uuid.UUID
    grace: Person
    site: Site
    envelope: uuid.UUID
    signer: uuid.UUID
    tax_return: uuid.UUID
    work_item: uuid.UUID

    @property
    def system(self) -> TenantContext:
        return TenantContext(self.tenant, "system", "tax.filing")

    @property
    def given(self) -> EnvelopeInput:
        return EnvelopeInput(str(self.tenant), str(self.envelope))


async def _completed(net: Net) -> tuple[Signed, str]:
    """A `tax_return` Form 8879 for one work item, sent, signed at the fake and recorded."""
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "WITH t AS (SELECT set_config('app.tenant_id', $1::text, true)) "
        "INSERT INTO retention_policies (tenant_id, record_type, service_line, firm_years, "
        "clock_start_event, updated_by) SELECT $1::uuid, 'signature_evidence', 'any', 7, "
        "'event_date', 'test-seed' FROM t",
        str(tenant),
    )
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Feld")
    await seed.member(site, grace, "manager")
    work_item = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, kind, name, created_by) "
            "VALUES ($1, $2, $3, 'tax_return', 'TY2025 1040', $4) RETURNING id",
            tenant,
            site.engagement_id,
            site.client_id,
            admin.user_id,
        ),
    )
    envelope, signer, tax_return, now = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), datetime.now(UTC)
    contact = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
        "VALUES ($1, $2, 'Claire Feld', 'client_person') RETURNING id",
        tenant,
        site.client_id,
    )
    await seed.run_untriggered_many(
        [
            (
                "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, "
                "source_kind, source_id, client_id, engagement_id, work_item_id, title, "
                "provider, status, drafted_by_kind, drafted_by, sent_by, sent_at) VALUES ($1, "
                "$2, 2, 'form_8879', 'efile_authorization', 'tax_return', $3, $4, $5, $6, "
                "'TY2025 Form 8879', 'fake', 'sent', 'human', $7, $7, $8)",
                (
                    envelope,
                    tenant,
                    tax_return,
                    site.client_id,
                    site.engagement_id,
                    work_item,
                    grace.user_id,
                    now,
                ),
            ),
            (
                'INSERT INTO envelope_documents (tenant_id, envelope_id, "order", '
                "evidence_version_id, sha256) VALUES ($1, $2, 1, $3, $4)",
                (tenant, envelope, site.version_id, "a" * 64),
            ),
            (
                'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", party_kind, '
                "contact_id, identity_method) VALUES ($1, $2, $3, 1, 'contact', $4, 'kba')",
                (signer, tenant, envelope, contact),
            ),
            (
                "INSERT INTO approval_grants (tenant_id, subject_type, subject_id, action, "
                "approver_user_id, engagement_id, payload_sha256, not_before, expires_at, "
                "used_at, consumer_ref) VALUES ($1, 'envelope', $2, 'envelope.send', $3, $4, "
                "$5, $6, $7, $6, gen_random_uuid())",
                (
                    tenant,
                    envelope,
                    grace.user_id,
                    site.engagement_id,
                    "e" * 64,
                    now - timedelta(minutes=1),
                    now + timedelta(hours=1),
                ),
            ),
        ]
    )
    signed = Signed(net, tenant, grace, site, envelope, signer, tax_return, work_item)
    assert (await activities.envelope_send(signed.given)).status == "sent"
    pid = str(
        await seed.value("SELECT provider_envelope_id FROM envelopes WHERE id = $1", envelope)
    )
    return signed, pid


def _ctx(s: Signed) -> AuthContext:
    return AuthContext(
        TenantContext(s.tenant, "human", str(s.grace.user_id)),
        s.grace.user_id,
        uuid.uuid4(),
        None,
        None,
    )


async def _record(net: Net, fake: FakeEsign) -> Signed:
    s, pid = await _completed(net)
    fake.sign(pid, str(s.signer))
    assert await activities.envelope_poll(s.given) == "completed"
    assert await activities.envelope_complete(s.given) == "recorded"
    return s


# --- The acceptance: extend_retention only extends --------------------------------------------


async def test_ac_a_shortening_extend_retention_call_is_refused(
    net: Net, fake: FakeEsign, raw: S3Client
) -> None:
    s = await _record(net, fake)
    floor = await net.seed.value(
        "SELECT max(retain_until) FROM signature_evidence WHERE envelope_id = $1", s.envelope
    )
    assert isinstance(floor, date)
    with pytest.raises(RetentionNotExtended):
        await extend_retention(s.system, s.envelope, floor - timedelta(days=1))
    later = floor + timedelta(days=400)
    assert await extend_retention(s.system, s.envelope, later) == later
    assert await extend_retention(s.system, s.envelope, later) == later  # the same date: no-op
    with pytest.raises(RetentionNotExtended):
        await extend_retention(s.system, s.envelope, later - timedelta(days=1))
    # Every stored record of the envelope is locked until at least the new date.
    package = await net.seed.value(
        "SELECT package_key FROM signature_evidence WHERE envelope_id = $1", s.envelope
    )
    head = raw.head_object(Bucket=RECORDS, Key=str(package))
    assert head["ObjectLockMode"] == "COMPLIANCE"
    assert head["ObjectLockRetainUntilDate"].date() >= later
    # Beneath the service, 0432's trigger refuses a shorter date or clearing it.
    for value in (later - timedelta(days=1), None):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await net.seed.run(
                "UPDATE envelopes SET retain_until = $2 WHERE id = $1", s.envelope, value
            )
    assert "envelope.retention_extended" in await net.seed.actions(s.tenant)


# --- The superseded marker ---------------------------------------------------------------------


async def test_the_system_supersedes_once_nobody_clears_it_and_the_gate_is_unmet(
    net: Net, fake: FakeEsign
) -> None:
    s = await _record(net, fake)
    met = await envelope_gate_facts(_ctx(s), EFILE_GATE, s.tax_return)
    assert met.met and met.envelope_id == s.envelope

    person = TenantContext(s.tenant, "human", str(s.grace.user_id))
    agent = TenantContext(s.tenant, "agent", "agent:tax.preparer:run")
    for who in (person, agent):
        with pytest.raises(SystemOnly):
            await supersede_for_amount_change(who, s.envelope, "binding-agi-51")
    assert await supersede_for_amount_change(s.system, s.envelope, "binding-agi-51")
    assert not await supersede_for_amount_change(s.system, s.envelope, "binding-agi-51")

    unmet = await envelope_gate_facts(_ctx(s), EFILE_GATE, s.tax_return)
    assert not unmet.met
    row = await net.seed.rows(
        "SELECT status, superseded_reason, superseded_binding_ref FROM envelopes WHERE id = $1",
        s.envelope,
    )
    assert dict(row[0]) == {
        "status": "completed",  # the evidence and the status stay
        "superseded_reason": "amount_change",
        "superseded_binding_ref": "binding-agi-51",
    }
    with pytest.raises(asyncpg.InsufficientPrivilegeError):  # nobody clears it
        await net.seed.run("UPDATE envelopes SET superseded_at = NULL WHERE id = $1", s.envelope)
    published = await net.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'envelope.superseded'",
        s.tenant,
    )
    assert published == 1


async def test_the_database_refuses_a_person_setting_the_marker(net: Net, fake: FakeEsign) -> None:
    s = await _record(net, fake)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await net.seed.run(
            "WITH t AS (SELECT set_config('app.actor_kind', 'human', true)) "
            "UPDATE envelopes SET superseded_at = now(), superseded_reason = 'amount_change' "
            "FROM t WHERE id = $1",
            s.envelope,
        )


# --- TAX-01's chips and the signer-level events --------------------------------------------------


async def test_chips_come_per_work_item_and_the_poll_emits_signer_events(
    net: Net, fake: FakeEsign
) -> None:
    s, pid = await _completed(net)
    before = await envelope_summaries_for(_ctx(s), [s.work_item])
    (only,) = before[s.work_item]
    assert (only.envelope_id, only.status, only.signed, only.total) == (s.envelope, "sent", 0, 1)
    assert [(c.first_name, c.status) for c in only.chips] == [("Claire", "pending")]

    fake.sign(pid, str(s.signer))
    await activities.envelope_poll(s.given)
    after = (await envelope_summaries_for(_ctx(s), [s.work_item]))[s.work_item][0]
    assert after.signed == 1 and after.chips[0].status == "signed"
    assert not after.superseded
    events = await net.seed.rows(
        "SELECT event_type, payload->>'signer_id' AS signer, payload->>'source_kind' AS kind "
        "FROM outbox WHERE tenant_id = $1 AND event_type LIKE 'envelope.signer_%'",
        s.tenant,
    )
    assert [(e["event_type"], e["signer"], e["kind"]) for e in events] == [
        ("envelope.signer_signed", str(s.signer), TAX_RETURN)
    ]
    assert await envelope_summaries_for(_ctx(s), []) == {}
