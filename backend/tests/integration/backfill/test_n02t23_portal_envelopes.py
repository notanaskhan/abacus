# ac-test-author: ayushkbhatia
"""N-02-T23 (TASK-2231; N-02 §3.4; SPEC-381 AC-10-AC-12; DF-11, DF-12; DEC-1283): POR-06's
portal envelope routes, live on the fake provider.

Acceptance (the task row): "Owen Calder signs E13 on staging through the demo account, the return
page shows Completed only after the poll, and Jonah Feld cannot open Claire's session." The
staging walk is the demo account's; here the same path runs over HTTP against the fake: Owen's
return answers pending until the provider reports him signed, and Jonah's principal never
reaches Claire's session.

Also: ERSD consent before any session; the refusals `mfa_required`, `not_your_turn`,
`before_date_as_of` and `declined`; a portal decline withdraws, a provider's is final; the
signed copy carries the evidence pages and each download is audited; a firm principal and a
person who is not a signer see nothing.

Boundary: HTTP through `create_app()` with fake-identity tokens; the fake provider driven as a
signer would; outcomes through the responses, SQL and the audit trail.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final, cast

import pypdfium2 as pdfium
import pytest

from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import records, storage
from abacus.modules.signatures import activities, status_poll
from abacus.modules.signatures.api import EnvelopeInput, configure_provider
from abacus_tools.fakes.esign import FakeEsign

from .support import Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response body as the contract shapes it
FLAGS: Final = ("signatures.envelopes", "signatures.esign_provider")
EVIDENCE: Final = "n02t23-evidence"
RECORDS: Final = "n02t23-records"
MASTER: Final = b"n02t23-independent-master-key-0123456789"
BASE: Final = "/v1/portal/envelopes"


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
def fake(raw: S3Client, monkeypatch: pytest.MonkeyPatch) -> Iterator[FakeEsign]:
    settings.cache_clear()
    forget_flags()
    reset_key_service()
    configure_key_service(LocalKeyService(MASTER))
    storage.configure_storage(raw, EVIDENCE)
    records.configure_records(raw, RECORDS)
    provider = FakeEsign()
    configure_provider(provider)

    async def hinted(tenant_id: uuid.UUID, envelope_id: uuid.UUID) -> None:
        del tenant_id, envelope_id  # no worker here: the routes' own poll is what is tested

    monkeypatch.setattr(status_poll, "hint_envelope", hinted)
    yield provider
    configure_provider(None)
    records.reset_records()
    storage.reset_storage()
    reset_key_service()
    forget_flags()


@dataclass(frozen=True)
class World:
    net: Net
    tenant: uuid.UUID
    grace: Person
    site: Site
    disclosure: uuid.UUID


async def _world(net: Net) -> World:
    seed = net.seed
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'N-02-T23')",
            tenant,
            flag,
        )
    await seed.run(
        "WITH t AS (SELECT set_config('app.tenant_id', $1::text, true)) "
        "INSERT INTO retention_policies (tenant_id, record_type, service_line, firm_years, "
        "clock_start_event, updated_by) SELECT $1::uuid, 'signature_evidence', 'any', 7, "
        "'event_date', 'test-seed' FROM t",
        str(tenant),
    )
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Calder")
    await seed.member(site, grace, "manager")
    disclosure = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO esign_disclosures (tenant_id, version_no, body, body_sha256, "
            "imported_by) VALUES ($1, 1, 'You agree to sign electronically.', $2, $3) "
            "RETURNING id",
            tenant,
            "c" * 64,
            admin.user_id,
        ),
    )
    return World(net, tenant, grace, site, disclosure)


async def _signer(w: World, name: str) -> Person:
    """A client person on the engagement, with their own contact (linked by `user_id`)."""
    who = await w.net.seed.client_contact(w.site)
    await w.net.seed.run(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, user_id) "
        "VALUES ($1, $2, $3, 'client_person', $4)",
        w.tenant,
        w.site.client_id,
        name,
        who.user_id,
    )
    return who


async def _send(
    w: World,
    people: list[Person],
    *,
    signer_order: str = "sequential",
    date_as_of: date | None = None,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """An envelope Grace sent to `people`, created at the fake provider by EnvelopeWorkflow's
    send activity (as the worker runs it)."""
    seed = w.net.seed
    envelope = uuid.uuid4()
    now = datetime.now(UTC)
    statements: list[tuple[str, tuple[object, ...]]] = [
        (
            "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, client_id, "
            "engagement_id, title, provider, status, signer_order, date_as_of_mode, date_as_of, "
            "drafted_by_kind, drafted_by, sent_by, sent_at, expires_at) VALUES ($1, $2, "
            "(SELECT coalesce(max(number), 0) + 13 FROM envelopes WHERE tenant_id = $2), "
            "'engagement_letter', 'engagement_letter', $3, $4, 'Ridgeline engagement letter', "
            "'fake', 'sent', $5, $6, $7, 'human', $8, $8, $9, $10)",
            (
                envelope,
                w.tenant,
                w.site.client_id,
                w.site.engagement_id,
                signer_order,
                "none" if date_as_of is None else "fixed_date",
                date_as_of,
                w.grace.user_id,
                now,
                now + timedelta(days=20),
            ),
        ),
        (
            'INSERT INTO envelope_documents (tenant_id, envelope_id, "order", '
            "evidence_version_id, sha256) VALUES ($1, $2, 1, $3, $4)",
            (w.tenant, envelope, w.site.version_id, "d" * 64),
        ),
        (
            # The send's grant, consumed by the relay for its sender (N-02-T22, DEC-1284).
            "INSERT INTO approval_grants (tenant_id, subject_type, subject_id, action, "
            "approver_user_id, engagement_id, payload_sha256, not_before, expires_at, used_at, "
            "consumer_ref) VALUES ($1, 'envelope', $2, 'envelope.send', $3, $4, $5, $6, $7, $6, "
            "gen_random_uuid())",
            (
                w.tenant,
                envelope,
                w.grace.user_id,
                w.site.engagement_id,
                "e" * 64,
                now - timedelta(minutes=1),
                now + timedelta(hours=1),
            ),
        ),
    ]
    ids: list[uuid.UUID] = []
    for order, who in enumerate(people, start=1):
        contact = await seed.value(
            "SELECT id FROM contacts WHERE tenant_id = $1 AND user_id = $2", w.tenant, who.user_id
        )
        signer = uuid.uuid4()
        ids.append(signer)
        statements.append(
            (
                'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", party_kind, '
                "contact_id, identity_method) VALUES ($1, $2, $3, $4, 'contact', $5, "
                "'email_code')",
                (signer, w.tenant, envelope, order, contact),
            )
        )
    await seed.run_untriggered_many(statements)
    plan = await activities.envelope_send(EnvelopeInput(str(w.tenant), str(envelope)))
    assert plan.status == "sent"
    return envelope, ids


async def _pid(w: World, envelope: uuid.UUID) -> str:
    return cast(
        str,
        await w.net.seed.value(
            "SELECT provider_envelope_id FROM envelopes WHERE id = $1", envelope
        ),
    )


async def _ok(
    w: World, method: str, path: str, who: Person, body: Body | None = None, *, mfa: bool = True
) -> Body:
    headers = w.net.headers(who, mfa=mfa)
    if path.endswith("/signing-session"):
        headers["Idempotency-Key"] = uuid.uuid4().hex
    response = await w.net.http.request(method, path, json=body, headers=headers)
    assert response.status_code == 200, response.text
    return cast(Body, response.json())


async def _refused(
    w: World, path: str, who: Person, *, mfa: bool = True, key: str | None = None
) -> tuple[int, str]:
    headers = w.net.headers(who, mfa=mfa) | {"Idempotency-Key": key or uuid.uuid4().hex}
    response = await w.net.http.post(path, headers=headers)
    code = cast(Body, response.json()).get("detail") if response.content else None
    return response.status_code, str(code)


async def _consent(w: World, envelope: uuid.UUID, who: Person) -> None:
    await _ok(
        w,
        "POST",
        f"{BASE}/{envelope}/esign-consent",
        who,
        {"disclosure_version_id": str(w.disclosure)},
    )


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_owen_signs_and_the_return_shows_completed_only_after_the_poll(
    net: Net, fake: FakeEsign
) -> None:
    w = await _world(net)
    owen = await _signer(w, "Owen Calder")
    envelope, (signer,) = await _send(w, [owen])

    listed = await _ok(w, "GET", BASE, owen)
    assert [r["id"] for r in listed["items"]] == [str(envelope)]
    view = await _ok(w, "GET", f"{BASE}/{envelope}", owen)
    assert view["esign_consent_needed"] is True
    assert view["disclosure_version_id"] == str(w.disclosure)
    assert view["outcome"] is None

    # ERSD before any session (ESIGN Act): refused, then accepted and stored once.
    assert await _refused(w, f"{BASE}/{envelope}/signing-session", owen) == (
        409,
        "esign_consent_required",
    )
    await _consent(w, envelope, owen)
    await _consent(w, envelope, owen)  # a repeat stores nothing twice
    assert (
        await net.seed.value("SELECT count(*) FROM esign_acceptances WHERE signer_id = $1", signer)
        == 1
    )

    session = await _ok(w, "POST", f"{BASE}/{envelope}/signing-session", owen)
    assert session["presentation"] == "redirect"  # DocuSeal refuses framing (DF-12)
    assert session["url"].startswith("https://")
    stored = await net.seed.value(
        "SELECT count(*) FROM signing_sessions WHERE id = $1 AND principal_id = $2 "
        "AND state = 'issued'",
        uuid.UUID(session["session_id"]),
        owen.user_id,
    )
    assert stored == 1
    back = f"{BASE}/{envelope}/signing-session/{session['session_id']}/return"

    # Back before the provider has him signed (or with a forged parameter): nothing completes.
    early = await _ok(w, "GET", f"{back}?status=completed&event=signing_complete", owen)
    assert early["outcome"] is None
    assert early["row"]["status"] == "sent"
    assert early["row"]["my_status"] == "pending"

    fake.sign(await _pid(w, envelope), str(signer))
    done = await _ok(w, "GET", back, owen)
    assert done["outcome"] == "signed"
    assert done["row"]["status"] == "completed"  # only after the poll read the provider
    assert done["signers_signed"] == done["signers_total"] == 1
    state = await net.seed.value(
        "SELECT state FROM signing_sessions WHERE id = $1", uuid.UUID(session["session_id"])
    )
    assert state == "confirmed"
    assert (await _ok(w, "GET", BASE, owen))["items"] == []  # nothing left to sign
    signed = await _ok(w, "GET", f"{BASE}?status=signed", owen)
    assert [r["id"] for r in signed["items"]] == [str(envelope)]


async def test_ac_jonah_cannot_open_claires_session(net: Net, fake: FakeEsign) -> None:
    w = await _world(net)
    claire = await _signer(w, "Claire Feld")
    jonah = await _signer(w, "Jonah Feld")
    envelope, (claire_signer, jonah_signer) = await _send(
        w, [claire, jonah], signer_order="parallel"
    )
    await _consent(w, envelope, claire)
    claires = await _ok(w, "POST", f"{BASE}/{envelope}/signing-session", claire)

    # Claire's session is Claire's: Jonah's principal reaches nothing of it.
    response = await net.http.get(
        f"{BASE}/{envelope}/signing-session/{claires['session_id']}/return",
        headers=net.headers(jonah),
    )
    assert response.status_code == 404, response.text
    # Jonah's own consent and session are his signer row's, never Claire's.
    await _consent(w, envelope, jonah)
    jonahs = await _ok(w, "POST", f"{BASE}/{envelope}/signing-session", jonah)
    assert jonahs["session_id"] != claires["session_id"]
    assert jonahs["url"] != claires["url"]
    rows = await net.seed.rows(
        "SELECT signer_id, principal_id FROM signing_sessions WHERE envelope_id = $1", envelope
    )
    assert {(r["signer_id"], r["principal_id"]) for r in rows} == {
        (claire_signer, claire.user_id),
        (jonah_signer, jonah.user_id),
    }
    accepted = await net.seed.rows(
        "SELECT signer_id FROM esign_acceptances WHERE signer_id = ANY($1::uuid[])",
        [claire_signer, jonah_signer],
    )
    assert {r["signer_id"] for r in accepted} == {claire_signer, jonah_signer}


# --- Refusals ------------------------------------------------------------------------------------


async def test_a_session_is_refused_without_mfa_out_of_turn_and_before_date_as_of(
    net: Net, fake: FakeEsign
) -> None:
    w = await _world(net)
    first = await _signer(w, "Dana Kowalski")
    second = await _signer(w, "Owen Calder")
    envelope, _ = await _send(w, [first, second])
    for who in (first, second):
        await _consent(w, envelope, who)
    path = f"{BASE}/{envelope}/signing-session"
    assert await _refused(w, path, first, mfa=False) == (409, "mfa_required")
    assert await _refused(w, path, second) == (409, "not_your_turn")

    later = date.today() + timedelta(days=10)
    dated, _ = await _send(w, [first], date_as_of=later)
    await _consent(w, dated, first)
    status, code = await _refused(w, f"{BASE}/{dated}/signing-session", first)
    assert (status, code) == (409, "before_date_as_of")


async def test_a_firm_principal_and_a_person_who_is_not_a_signer_see_nothing(
    net: Net, fake: FakeEsign
) -> None:
    w = await _world(net)
    owen = await _signer(w, "Owen Calder")
    other = await _signer(w, "Rosa Calder")  # on the engagement, not on this envelope
    envelope, _ = await _send(w, [owen])
    for who in (w.grace, other):
        response = await net.http.get(f"{BASE}/{envelope}", headers=net.headers(who))
        assert response.status_code == 404, response.text
    assert (await _ok(w, "GET", BASE, other))["items"] == []


# --- Decline and withdraw ------------------------------------------------------------------------


async def test_a_portal_decline_refuses_sessions_and_withdraws_but_a_provider_one_is_final(
    net: Net, fake: FakeEsign
) -> None:
    w = await _world(net)
    owen = await _signer(w, "Owen Calder")
    envelope, (signer,) = await _send(w, [owen])
    await _consent(w, envelope, owen)
    declined = await _ok(
        w,
        "POST",
        f"{BASE}/{envelope}/decline",
        owen,
        {"reason": "have_questions", "note": "Is the fee right?"},
    )
    assert declined["row"]["status"] == "declined"
    assert declined["outcome"] == "declined"
    assert await _refused(w, f"{BASE}/{envelope}/signing-session", owen) == (409, "declined")

    back = await _ok(w, "POST", f"{BASE}/{envelope}/decline/withdraw", owen)
    assert back["row"]["status"] == "sent"
    assert back["row"]["my_status"] == "pending"
    assert (
        await net.seed.value("SELECT decline_reason FROM envelope_signers WHERE id = $1", signer)
        is None
    )

    # Declined inside the provider view: final.
    fake.decline(await _pid(w, envelope), str(signer), "other")
    assert await activities.envelope_poll(EnvelopeInput(str(w.tenant), str(envelope))) == (
        "declined"
    )
    response = await net.http.post(
        f"{BASE}/{envelope}/decline/withdraw", headers=net.headers(owen)
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "decline_not_withdrawable"
    actions = await net.seed.actions(w.tenant)
    assert {"envelope.declined", "envelope.decline_withdrawn"} <= set(actions)


# --- The signed copy -----------------------------------------------------------------------------


async def test_the_signed_copy_carries_the_evidence_pages_and_each_download_is_audited(
    net: Net, fake: FakeEsign
) -> None:
    w = await _world(net)
    owen = await _signer(w, "Owen Calder")
    envelope, (signer,) = await _send(w, [owen])
    early = await net.http.get(f"{BASE}/{envelope}/download", headers=net.headers(owen))
    assert early.status_code == 409, early.text
    assert early.json()["detail"] == "signed_copy_not_ready"

    fake.sign(await _pid(w, envelope), str(signer))
    given = EnvelopeInput(str(w.tenant), str(envelope))
    assert await activities.envelope_poll(given) == "completed"
    assert await activities.envelope_complete(given) == "recorded"

    for _ in range(2):
        got = await net.http.get(f"{BASE}/{envelope}/download", headers=net.headers(owen))
        assert got.status_code == 200, got.text
        assert got.headers["content-type"] == "application/pdf"
        assert got.headers["cache-control"] == "private, no-store"
        assert got.content.startswith(b"%PDF")
        merged = pdfium.PdfDocument(got.content)
        assert len(merged) == 2  # the signed document, then the provider's evidence page
        merged.close()
    actions = await net.seed.actions(w.tenant)
    assert actions.count("signed_copy.downloaded") == 2
