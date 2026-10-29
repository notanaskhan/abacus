# ac-test-author: n02t16-independent
"""N-02-T16 (TASK-2017; ADR-078): independent acceptance tests for N-02-T13 and N-02-T14, written
from N-02 §3.2, §3.3, §3.7 and SPEC-381 AC-4-AC-6, AC-17, not from the builders' tests.

Acceptance (the task row): "The suite passes and fails if a reminder exceeds the policy cap or a
package lacks the identity result."

Paths the builders' suites do not take: an envelope on a client alone (no engagement) behind a
wall; the cap from a firm's own policy row; a Saturday send; the five IRS items read back through
the evidence zip the route serves; a void on a declined envelope; a reveal of an address the
import never recorded. The replay is `tests/workflows/test_envelope_replay.py`.

Boundary: HTTP through `create_app()` and the workflow's activities; SQL and S3 for outcomes.
"""

from __future__ import annotations

import io
import json
import uuid
import zipfile
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, cast
from zoneinfo import ZoneInfo

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
Body = dict[str, Any]  # a response body as the contract shapes it
FLAG: Final = "signatures.envelopes"
EVIDENCE: Final = "n02t16-evidence"
RECORDS: Final = "n02t16-records"
MASTER: Final = b"n02t16-independent-master-key-0123456789"
IRS_ITEMS: Final = ("signed_image_sha256", "signed_at", "login_ref", "identity_result")


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


async def _firm(net: Net) -> tuple[uuid.UUID, Person, Person, Person, Site, Site]:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'N-02-T16')",
        tenant,
        FLAG,
    )
    await seed.run(
        "WITH t AS (SELECT set_config('app.tenant_id', $1::text, true)) "
        "INSERT INTO retention_policies (tenant_id, record_type, service_line, firm_years, "
        "clock_start_event, updated_by) SELECT $1::uuid, 'signature_evidence', 'any', 7, "
        "'event_date', 'test-seed' FROM t",
        str(tenant),
    )
    admin = await seed.person(tenant, "firm_admin")
    lena = await seed.person(tenant, "firm_admin")  # walled from Ashford
    grace = await seed.person(tenant, "firm_admin")
    open_site = await seed.site(tenant, admin.user_id, "Feld")
    ashford = await seed.site(tenant, admin.user_id, "Ashford")
    for site in (open_site, ashford):
        for who in (lena, grace):
            await seed.member(site, who, "manager")
    await net.wall(admin, lena, ashford)
    return tenant, admin, lena, grace, open_site, ashford


async def _envelope(
    net: Net,
    tenant: uuid.UUID,
    site: Site,
    sender: Person,
    *,
    status: str = "sent",
    engagement: bool = True,
    purpose: str = "consent_7216",
    signers: int = 1,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    envelope = uuid.uuid4()
    now = datetime.now(UTC)
    family = "efile_authorization" if purpose.startswith("form_8879") else "consent"
    statements: list[tuple[str, tuple[object, ...]]] = [
        (
            "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, client_id, "
            "engagement_id, title, provider, status, drafted_by_kind, drafted_by, sent_by, "
            "sent_at, expires_at, reminder_cadence) VALUES ($1, $2, "
            "(SELECT coalesce(max(number), 0) + 1 FROM envelopes WHERE tenant_id = $2), $3, $4, "
            "$5, $6, 'Separate §7216 consent', 'fake', $7, 'human', $8, $8, $9, $10, 'daily')",
            (
                envelope,
                tenant,
                purpose,
                family,
                site.client_id,
                site.engagement_id if engagement else None,
                status,
                sender.user_id,
                now,
                now + timedelta(days=30),
            ),
        ),
        (
            'INSERT INTO envelope_documents (tenant_id, envelope_id, "order", '
            "evidence_version_id, sha256) VALUES ($1, $2, 1, $3, $4)",
            (tenant, envelope, site.version_id, "b" * 64),
        ),
    ]
    ids: list[uuid.UUID] = []
    for order in range(1, signers + 1):
        contact = await net.seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, $3, 'client_person') RETURNING id",
            tenant,
            site.client_id,
            f"Feld signer {order}",
        )
        signer = uuid.uuid4()
        ids.append(signer)
        state = "declined" if status == "declined" and order == 1 else "pending"
        statements.append(
            (
                'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", party_kind, '
                "contact_id, identity_method, status, decline_reason) VALUES "
                "($1, $2, $3, $4, 'contact', $5, 'email_code', $6, $7)",
                (
                    signer,
                    tenant,
                    envelope,
                    order,
                    contact,
                    state,
                    "something_wrong" if state == "declined" else None,
                ),
            )
        )
    await net.seed.run_untriggered_many(statements)
    return envelope, ids


async def _get(net: Net, who: Person, path: str, **params: str | int) -> Body:
    response = await net.http.get(path, params=params, headers=net.headers(who))
    assert response.status_code == 200, response.text
    return cast(Body, response.json())


# --- T13: counts foot and omit walled rows, including client-only envelopes ---------------------


async def test_a_walled_client_only_envelope_is_in_no_row_count_or_tile(net: Net) -> None:
    tenant, _admin, lena, grace, feld, ashford = await _firm(net)
    for _ in range(3):
        await _envelope(net, tenant, feld, grace)
    walled, _ = await _envelope(net, tenant, ashford, grace, engagement=False)

    hers = await _get(net, lena, "/v1/envelopes", tab="out")
    assert hers["total"] == len(hers["items"]) == 3
    assert str(walled) not in {r["id"] for r in hers["items"]}
    assert sum(hers["counts"].get(k, 0) for k in ("sent", "viewed", "partially_signed")) == 3
    summary = await _get(net, lena, "/v1/envelopes/summary")
    assert summary["out"] == 3
    assert sum(t["n"] for t in summary["by_type"]) == summary["out"]
    missing = await net.call("GET", f"/v1/envelopes/{walled}", lena)
    assert missing.status_code == 404

    theirs = await _get(net, grace, "/v1/envelopes", tab="out")
    assert theirs["total"] == 4


# --- T13: reveal, void ---------------------------------------------------------------------------


async def test_a_reveal_of_an_address_never_recorded_is_refused_not_invented(
    net: Net, fake: FakeEsign
) -> None:
    tenant, _admin, _lena, grace, feld, _ashford = await _firm(net)
    envelope, signers = await _envelope(net, tenant, feld, grace)
    path = f"/v1/envelopes/{envelope}/signers/{signers[0]}/reveal-ip"
    no_mfa = await net.call("POST", path, grace, body={"reason": "IRS inquiry"}, mfa=False)
    assert no_mfa.status_code in (401, 403)
    none_yet = await net.call("POST", path, grace, body={"reason": "IRS inquiry"})
    assert none_yet.status_code == 404  # no evidence row: nothing to reveal
    audited = await net.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'signer.ip_revealed'",
        tenant,
    )
    assert audited == 0


async def test_a_declined_envelope_cannot_be_voided_and_keeps_its_rows(net: Net) -> None:
    tenant, _admin, _lena, grace, feld, _ashford = await _firm(net)
    envelope, _ = await _envelope(net, tenant, feld, grace, status="declined")
    refused = await net.call(
        "POST", f"/v1/envelopes/{envelope}/void", grace, body={"reason": "replaced"}
    )
    assert refused.status_code == 409
    status = await net.seed.value("SELECT status FROM envelopes WHERE id = $1", envelope)
    assert status == "declined"
    bad_reason = await net.call(
        "POST", f"/v1/envelopes/{envelope}/void", grace, body={"reason": "because"}
    )
    assert bad_reason.status_code == 422


# --- T14: the reminder cap and weekday timing ----------------------------------------------------


async def test_a_reminder_never_exceeds_the_firms_own_cap(net: Net, fake: FakeEsign) -> None:
    tenant, _admin, _lena, grace, feld, _ashford = await _firm(net)
    await net.seed.run_untriggered(
        "INSERT INTO envelope_policies (tenant_id, policy_family, purpose, "
        "allowed_identity_methods, default_identity_method, max_reminders) "
        "VALUES ($1, 'consent', 'consent_7216', ARRAY['email_code'], 'email_code', 1)",
        tenant,
    )
    envelope, _ = await _envelope(net, tenant, feld, grace)
    given = EnvelopeInput(str(tenant), str(envelope))
    plan = await activities.envelope_send(given)
    assert len(plan.reminders) <= 1

    async def sender(_t: TenantContext, _e: uuid.UUID, _s: uuid.UUID, _n: int) -> bool:
        return True

    register_reminder_sender(sender)
    due = ReminderDue(str(tenant), str(envelope), 1)
    outcomes = [await activities.envelope_remind(due) for _ in range(3)]
    assert outcomes == ["sent", "capped", "capped"]
    sent = await net.seed.value(
        "SELECT count(*) FROM envelope_events "
        "WHERE envelope_id = $1 AND kind = 'envelope.reminded'",
        envelope,
    )
    assert sent == 1


def test_a_saturday_send_reminds_from_monday_at_nine_local_never_on_a_weekend() -> None:
    saturday = datetime(2026, 10, 31, 18, 0, tzinfo=UTC)
    out = reminder_instants(
        cadence="daily",
        sent_at=saturday,
        expires_at=saturday + timedelta(days=30),
        cap=5,
        zone="America/New_York",
    )
    assert len(out) == 5
    for at in out:
        local = at.astimezone(ZoneInfo("America/New_York"))
        assert local.weekday() < 5
        assert (local.hour, local.minute) == (9, 0)
    assert out[0].date() == date(2026, 11, 2)
    weekly = reminder_instants(
        cadence="weekly",
        sent_at=saturday,
        expires_at=saturday + timedelta(days=8),
        cap=5,
        zone="UTC",
    )
    assert [a.date() for a in weekly] == [date(2026, 11, 6)]  # the next one would pass expiry


# --- T13 + T14: the five IRS items in every package, read back through the zip ------------------


async def test_every_package_in_the_evidence_zip_carries_the_five_irs_items(
    net: Net, fake: FakeEsign
) -> None:
    tenant, _admin, _lena, grace, feld, _ashford = await _firm(net)
    envelope, signers = await _envelope(net, tenant, feld, grace, signers=2)
    given = EnvelopeInput(str(tenant), str(envelope))
    await activities.envelope_send(given)
    pid = cast(
        str,
        await net.seed.value("SELECT provider_envelope_id FROM envelopes WHERE id = $1", envelope),
    )
    for signer in signers:
        fake.sign(pid, str(signer), ip="192.0.2.10")
    assert await activities.envelope_poll(given) == "completed"
    assert await activities.envelope_complete(given) == "recorded"

    first = await net.call("GET", f"/v1/envelopes/{envelope}/evidence.zip", grace)
    assert first.status_code == 200, first.text
    again = await net.call("GET", f"/v1/envelopes/{envelope}/evidence.zip", grace)
    assert again.content == first.content
    archive = zipfile.ZipFile(io.BytesIO(first.content))
    packages = [n for n in archive.namelist() if n.startswith("packages/")]
    assert len(packages) == 2
    for name in packages:
        package = json.loads(archive.read(name))
        for item in IRS_ITEMS:
            assert package.get(item), f"{name} lacks {item}"
        assert package["ip_masked"].startswith("192.0.") and package.get("ip_sealed")
        assert "192.0.2.10" not in archive.read(name).decode()
        assert package.get("signature_method")
    downloads = await net.seed.value(
        "SELECT count(*) FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'evidence.downloaded'",
        tenant,
    )
    assert downloads == 2
    completed = await net.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'envelope.completed'",
        tenant,
    )
    assert completed == 1
