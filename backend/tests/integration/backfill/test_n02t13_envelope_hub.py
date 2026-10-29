# ac-test-author: ayushkbhatia
"""N-02-T13 (TASK-2014; N-02 §3.2, §3.3; SIG-01 a; SPEC-381 AC-4-AC-6; DEC-20, DEC-33, DEC-43):
the firm envelope read models and actions, live.

Acceptance (the task row): "Grace Holloway's Out for signature tab returns 17 rows with tiles 8,
5, 4 and 4, and a walled engagement's envelope is absent with no count."

Also: the summary foots and leaves the walled row out; the drawer names the signers and shows
the masked address only; a reveal needs a reason and a recent second factor, answers `no-store`
and is audited; the evidence zip is audited and byte-identical on repeat; a void needs a reason,
keeps the evidence and is refused on a closed envelope; the flag off answers 404.

Boundary: `create_app()` over HTTP as each signed-in person; seeded rows through SQL.
"""

from __future__ import annotations

import hashlib
import io
import uuid
import zipfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Final, cast

import pytest

from abacus.kernel.clock import today
from abacus.kernel.config import settings
from abacus.kernel.crypto import LocalKeyService, configure_key_service, reset_key_service
from abacus.kernel.flags import forget_flags
from abacus.kernel.storage import s3_client
from abacus.modules.evidence import records, storage
from abacus.modules.signatures.hub import seal_ip

from .support import Net, Person, Site

if TYPE_CHECKING:
    from types_boto3_s3 import S3Client

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # a response body as the contract shapes it
FLAG: Final = "signatures.envelopes"
EVIDENCE: Final = "n02t13-evidence"
RECORDS: Final = "n02t13-records"
MASTER: Final = b"n02t13-independent-master-key-0123456789"
LETTER: Final = b"%PDF-1.7\n% Kowal 2025 Form 8879, signed\n%%EOF\n"
CERTIFICATE: Final = b"%PDF-1.7\n% Certificate of completion\n%%EOF\n"
IP: Final = "73.44.118.9"


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
    admin: Person
    grace: Person  # Firm Admin (client_service at the firm, DEC-20), walled from Ashford
    other: Person  # a Firm Admin with no wall
    kowal: Site
    ashford: Site
    thomas: uuid.UUID  # Kowal's signer contact
    irene: uuid.UUID


async def _contact(net: Net, site: Site, name: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await net.seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, $3, 'client_person') RETURNING id",
            site.tenant_id,
            site.client_id,
            name,
        ),
    )


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'N-02-T13')",
        tenant,
        FLAG,
    )
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    other = await seed.person(tenant, "firm_admin")
    kowal = await seed.site(tenant, admin.user_id, "Kowal")
    ashford = await seed.site(tenant, admin.user_id, "Ashford")
    for site in (kowal, ashford):
        await seed.member(site, grace, "manager")
        await seed.member(site, other, "manager")
    await net.wall(admin, grace, ashford)
    thomas = await _contact(net, kowal, "Thomas Kowal")
    irene = await _contact(net, kowal, "Irene Kowal")
    return Firm(net, tenant, admin, grace, other, kowal, ashford, thomas, irene)


_number = iter(range(1, 10_000))


async def _envelope(
    firm: Firm,
    site: Site,
    status: str,
    *,
    purpose: str = "form_8879",
    due_on: date | None = None,
    signed: int = 0,
) -> uuid.UUID:
    """One envelope with Thomas and Irene as signers, `signed` of them signed; the rows as
    EnvelopeWorkflow leaves them (sent by Grace), seeded with triggers off."""
    envelope = uuid.uuid4()
    sent = status != "draft"
    family = "efile_authorization" if purpose.startswith("form_8879") else "general"
    statements: list[tuple[str, tuple[object, ...]]] = [
        (
            "INSERT INTO envelopes (id, tenant_id, number, purpose, policy_family, client_id, "
            "engagement_id, title, provider, status, drafted_by_kind, drafted_by, sent_by, "
            "sent_at, due_on, completed_at, expires_at) VALUES ($1, $2, $3, $4, $5, $6, $7, "
            "'TY2025 Form 1040', 'fake', $8, 'human', $9, $10, $11, $12, $13, now() + "
            "interval '20 days')",
            (
                envelope,
                firm.tenant_id,
                next(_number),
                purpose,
                family,
                site.client_id,
                site.engagement_id,
                status,
                firm.grace.user_id,
                firm.grace.user_id if sent else None,
                date.today() if sent else None,
                due_on,
                date.today() if status == "completed" else None,
            ),
        )
    ]
    for order, contact in enumerate((firm.thomas, firm.irene), start=1):
        signer = uuid.uuid4()
        done = order <= signed
        statements.append(
            (
                'INSERT INTO envelope_signers (id, tenant_id, envelope_id, "order", party_kind, '
                "contact_id, identity_method, status, signed_at, signature_method) VALUES "
                "($1, $2, $3, $4, 'contact', $5, 'kba', $6, $7, $8)",
                (
                    signer,
                    firm.tenant_id,
                    envelope,
                    order,
                    contact,
                    "signed" if done else "pending",
                    date.today() if done else None,
                    "typed" if done else None,
                ),
            )
        )
        if done:
            sealed = await seal_ip(firm.tenant_id, signer, IP)
            statements.append(
                (
                    "INSERT INTO signature_evidence (tenant_id, envelope_id, signer_id, "
                    "signed_at, ip_sealed, ip_masked, identity_result, signature_method, "
                    "document_sha256s) VALUES ($1, $2, $3, now(), $4, '73.44.•••.•••', "
                    "'KBA passed · 4 of 4 questions', 'typed', $5)",
                    (firm.tenant_id, envelope, signer, sealed, ["0" * 64]),
                )
            )
    await firm.net.seed.run_untriggered_many(statements)
    return envelope


async def _hub(firm: Firm) -> dict[str, uuid.UUID]:
    """SIG-01 a at E0: 17 out (8 sent, 5 viewed, 4 partially signed; 4 due within 7 days), two
    drafts, one expired, one completed; and one sent envelope behind Grace's Ashford wall."""
    day = await today()
    soon, later = day + timedelta(days=3), day + timedelta(days=20)
    out: list[tuple[str, int]] = [("sent", 0)] * 8 + [("viewed", 0)] * 5
    out += [("partially_signed", 1)] * 4
    made: dict[str, uuid.UUID] = {}
    for i, (status, signed) in enumerate(out):
        purpose = "engagement_letter" if i in (8, 9, 10, 11) else "form_8879"
        made[f"out{i}"] = await _envelope(
            firm,
            firm.kowal,
            status,
            purpose=purpose,
            due_on=soon if i in (0, 8, 13, 14) else later,
            signed=signed,
        )
    for i in range(2):
        made[f"draft{i}"] = await _envelope(firm, firm.kowal, "draft")
    made["expired"] = await _envelope(firm, firm.kowal, "expired")
    made["completed"] = await _envelope(firm, firm.kowal, "completed", signed=2)
    made["walled"] = await _envelope(firm, firm.ashford, "sent", due_on=soon)
    return made


async def _get(firm: Firm, who: Person, path: str, **params: str | int) -> Body:
    response = await firm.net.http.get(path, params=params, headers=firm.net.headers(who))
    assert response.status_code == 200, response.text
    return cast(Body, response.json())


# --- The acceptance ------------------------------------------------------------------------------


async def test_ac_graces_out_tab_returns_17_rows_with_tiles_and_no_walled_row(
    firm: Firm,
) -> None:
    made = await _hub(firm)
    page = await _get(firm, firm.grace, "/v1/envelopes", tab="out", limit=100)
    ids = {r["id"] for r in page["items"]}
    assert len(page["items"]) == page["total"] == 17
    assert str(made["walled"]) not in ids
    tiles = page["counts"]
    assert (tiles["sent"], tiles["viewed"], tiles["partially_signed"], tiles["due"]) == (
        8,
        5,
        4,
        4,
    )
    assert tiles["sent"] + tiles["viewed"] + tiles["partially_signed"] == 17

    # In due order: the four due within 7 days first.
    dues = [r["due_on"] for r in page["items"]]
    assert dues == sorted(dues)
    partial = next(r for r in page["items"] if r["status"] == "partially_signed")
    assert (partial["signed"], partial["total"]) == (1, 2)
    assert [(c["name"], c["signed"]) for c in partial["signer_chips"]] == [
        ("Thomas", True),
        ("Irene", False),
    ]
    assert partial["number"].startswith("E")
    assert "envelope.void" in partial["allowed_actions"]

    # The summary foots over the same rows; the walled envelope counts nowhere.
    summary = await _get(firm, firm.grace, "/v1/envelopes/summary")
    assert (summary["to_send"], summary["out"], summary["completed"], summary["expired"]) == (
        2,
        17,
        1,
        1,
    )
    by_type = {t["key"]: t["n"] for t in summary["by_type"]}
    assert sum(by_type.values()) == 17
    assert (by_type["efile"], by_type["engagement_letter"]) == (13, 4)

    # Without the wall, the same tab has the Ashford envelope too.
    theirs = await _get(firm, firm.other, "/v1/envelopes", tab="out", limit=100)
    assert theirs["total"] == 18
    assert (await _get(firm, firm.other, "/v1/envelopes/summary"))["out"] == 18


async def test_tabs_and_search_stay_under_visible(firm: Firm) -> None:
    made = await _hub(firm)
    drafts = await _get(firm, firm.grace, "/v1/envelopes", tab="to_send")
    assert {r["id"] for r in drafts["items"]} == {str(made["draft0"]), str(made["draft1"])}
    assert all(r["allowed_actions"][:1] == ["envelope.draft"] for r in drafts["items"])
    found = await _get(firm, firm.grace, "/v1/envelopes", q="Ashford")
    assert found["total"] == 0
    paged = await _get(firm, firm.grace, "/v1/envelopes", tab="out", limit=10)
    assert len(paged["items"]) == 10 and paged["next_cursor"]
    rest = await _get(
        firm, firm.grace, "/v1/envelopes", tab="out", limit=10, cursor=paged["next_cursor"]
    )
    assert len(rest["items"]) == 7
    assert not {r["id"] for r in rest["items"]} & {r["id"] for r in paged["items"]}


async def test_the_drawer_masks_the_address_and_hides_walled_envelopes(firm: Firm) -> None:
    made = await _hub(firm)
    drawer = await _get(firm, firm.grace, f"/v1/envelopes/{made['completed']}")
    assert [s["name"] for s in drawer["signers"]] == ["Thomas Kowal", "Irene Kowal"]
    assert [e["ip_masked"] for e in drawer["evidence"]] == ["73.44.•••.•••"] * 2
    assert IP not in str(drawer)
    walled = await firm.net.call("GET", f"/v1/envelopes/{made['walled']}", firm.grace)
    assert walled.status_code == 404


async def test_a_reveal_needs_a_reason_and_mfa_and_is_audited(firm: Firm) -> None:
    made = await _hub(firm)
    drawer = await _get(firm, firm.grace, f"/v1/envelopes/{made['completed']}")
    path = f"/v1/envelopes/{made['completed']}/signers/{drawer['signers'][0]['id']}/reveal-ip"
    no_reason = await firm.net.call("POST", path, firm.grace, body={})
    assert no_reason.status_code == 422
    stale = await firm.net.call("POST", path, firm.grace, body={"reason": "IRS"}, mfa=False)
    assert stale.status_code in (401, 403), stale.text
    shown = await firm.net.call("POST", path, firm.grace, body={"reason": "IRS inquiry"})
    assert shown.status_code == 200, shown.text
    assert shown.json()["ip"] == IP
    assert shown.headers["cache-control"] == "no-store"
    audited = await firm.net.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action = 'signer.ip_revealed'",
        firm.tenant_id,
    )
    assert audited == 1


async def test_a_void_needs_a_reason_keeps_evidence_and_closes_the_envelope(firm: Firm) -> None:
    made = await _hub(firm)
    path = f"/v1/envelopes/{made['out13']}/void"
    assert (await firm.net.call("POST", path, firm.grace, body={})).status_code == 422
    voided = await firm.net.call("POST", path, firm.grace, body={"reason": "wrong_document"})
    assert voided.status_code == 200, voided.text
    assert voided.json()["row"]["status"] == "voided"
    assert voided.json()["voided_reason"] == "wrong_document"
    seed = firm.net.seed
    by = await seed.value("SELECT voided_by FROM envelopes WHERE id = $1", made["out13"])
    assert by == firm.grace.user_id
    kept = await seed.value(
        "SELECT count(*) FROM signature_evidence WHERE envelope_id = $1", made["out13"]
    )
    assert kept == 1
    again = await firm.net.call("POST", path, firm.grace, body={"reason": "replaced"})
    assert again.status_code == 409
    assert again.json()["detail"] == "envelope_not_open"
    walled = f"/v1/envelopes/{made['walled']}/void"
    assert (
        await firm.net.call("POST", walled, firm.grace, body={"reason": "replaced"})
    ).status_code == 404


async def _imported(firm: Firm) -> str:
    """A completed record-mode envelope with its files in the records bucket (N-02-T08)."""
    await firm.net.seed.run(
        "WITH t AS (SELECT set_config('app.tenant_id', $1::text, true)) "
        "INSERT INTO retention_policies (tenant_id, record_type, service_line, firm_years, "
        "clock_start_event, updated_by) SELECT $1::uuid, 'signature_evidence', 'any', 7, "
        "'event_date', 'test-seed' FROM t",
        str(firm.tenant_id),
    )
    uploads: list[str] = []
    for content, name in ((LETTER, "8879.pdf"), (CERTIFICATE, "certificate.pdf")):
        staged = await firm.net.http.post(
            "/v1/envelopes/import/files",
            params={
                "filename": name,
                "client_id": str(firm.kowal.client_id),
                "engagement_id": str(firm.kowal.engagement_id),
            },
            content=content,
            headers={**firm.net.headers(firm.grace), "Content-Type": "application/octet-stream"},
        )
        assert staged.status_code == 201, staged.text
        uploads.append(cast(Body, staged.json())["id"])
    response = await firm.net.http.post(
        "/v1/envelopes/import",
        json={
            "purpose": "form_8879",
            "client_id": str(firm.kowal.client_id),
            "engagement_id": str(firm.kowal.engagement_id),
            "title": "TY2025 Form 8879",
            "provider_name": "DocuSign",
            "signers": [
                {"contact_id": str(firm.thomas), "signed_on": "2026-09-10"}
                | {"identity_method": "kba"}
            ],
            "upload_ids": uploads,
            "attested": True,
        },
        headers={**firm.net.headers(firm.grace), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert response.status_code == 201, response.text
    return cast(str, response.json()["row"]["id"])


async def test_the_evidence_zip_is_audited_and_byte_identical(firm: Firm) -> None:
    envelope = await _imported(firm)
    path = f"/v1/envelopes/{envelope}/evidence.zip"
    first = await firm.net.call("GET", path, firm.grace)
    assert first.status_code == 200, first.text
    second = await firm.net.call("GET", path, firm.grace)
    assert first.content == second.content
    assert first.headers["cache-control"] == "no-store"
    archive = zipfile.ZipFile(io.BytesIO(first.content))
    names = archive.namelist()
    assert "manifest.sha256" in names
    for content in (LETTER, CERTIFICATE):
        assert f"documents/{hashlib.sha256(content).hexdigest()}" in names
    manifest = archive.read("manifest.sha256").decode().splitlines()
    for line in manifest:
        digest, name = line.split("  ", 1)
        assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    audited = await firm.net.seed.value(
        "SELECT count(*) FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'evidence.downloaded'",
        firm.tenant_id,
    )
    assert audited == 2


async def test_the_flag_off_answers_404(firm: Firm) -> None:
    await firm.net.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        firm.tenant_id,
        FLAG,
    )
    forget_flags()
    for path in ("/v1/envelopes", "/v1/envelopes/summary", f"/v1/envelopes/{uuid.uuid4()}"):
        assert (await firm.net.call("GET", path, firm.grace)).status_code == 404
