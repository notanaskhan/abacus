# ac-test-author: ayushkbhatia
"""N-02-T20 (TASK-2138; N-02 §3.4; SIG-02 a, f, g; DEC-24, DEC-1178): the envelope builder's
backend: a draft from a registered source, edits at a version, code-computed checks, Send with a
grant (+10 s) and Undo.

Acceptance (the task row): "A signer without an email blocks Send with 409 validation_failed, and
a send undone inside 10 seconds makes no provider call."

Boundary: `create_app()` over HTTP as a signed-in person; a test source registered through the
module's slot; outcomes through SQL.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Final, cast

import httpx
import pytest

from abacus.kernel.config import settings
from abacus.kernel.flags import forget_flags
from abacus.modules.identity.api import AuthContext
from abacus.modules.signatures.sources import (
    EnvelopeSource,
    SourceDocument,
    SourceDraft,
    SourceSigner,
    register_envelope_source,
)

from .support import Net, Person, Site

pytestmark = pytest.mark.asyncio
Body = dict[str, Any]  # Any: a response body as the contract shapes it
FLAG: Final = "signatures.envelopes"
KIND: Final = "test_n02t20_8879"


@dataclass(frozen=True)
class _Prefill:
    client_id: uuid.UUID
    engagement_id: uuid.UUID
    version_id: uuid.UUID
    sha256: str
    signer: uuid.UUID  # a contact
    ero: uuid.UUID  # a firm member


_PREFILLS: dict[uuid.UUID, _Prefill] = {}


async def _draft(ctx: AuthContext, source_id: uuid.UUID) -> SourceDraft:
    p = _PREFILLS[source_id]
    return SourceDraft(
        purpose="form_8879_pe",
        policy_family="efile_authorization",
        client_id=p.client_id,
        engagement_id=p.engagement_id,
        title="Form 8879-PE (2025)",
        form_code="8879-PE",
        documents=(SourceDocument(sha256=p.sha256, evidence_version_id=p.version_id),),
        signers=(
            SourceSigner(identity_method="kba", contact_id=p.signer),
            SourceSigner(identity_method="firm_sso", user_id=p.ero, role="ero"),
        ),
    )


async def _none(ctx: AuthContext, source_id: uuid.UUID) -> list[object]:
    return []


register_envelope_source(
    EnvelopeSource(
        kind=KIND,
        documents=_none,
        signers=_none,
        retention_record_type="signature_evidence",
        draft=_draft,
    )
)


@pytest.fixture(autouse=True)
def wired() -> Iterator[None]:
    settings.cache_clear()
    forget_flags()
    yield
    forget_flags()


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    grace: Person
    ero: Person
    site: Site
    sofia: uuid.UUID  # the signer contact, no email on file
    source_id: uuid.UUID  # the test source's record


@pytest.fixture
async def firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'N-02-T20')",
        tenant,
        FLAG,
    )
    admin = await seed.person(tenant, "firm_admin")
    grace = await seed.person(tenant, "firm_admin")
    ero = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, "Harborview")
    await seed.member(site, grace, "manager")
    sofia = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, 'Sofia Lindqvist', 'client_person') RETURNING id",
            tenant,
            site.client_id,
        ),
    )
    sha = cast(
        str,
        await seed.value(
            "SELECT fingerprint FROM evidence_versions WHERE id = $1", site.version_id
        ),
    )
    source_id = uuid.uuid4()
    _PREFILLS[source_id] = _Prefill(
        site.client_id, site.engagement_id, site.version_id, sha, sofia, ero.user_id
    )
    return Firm(net, tenant, grace, ero, site, sofia, source_id)


async def _call(
    firm: Firm, method: str, path: str, body: Body | None = None, **headers: str
) -> httpx.Response:
    sent = firm.net.headers(firm.grace, mfa=True, tenant=None) | {
        k.replace("_", "-").title(): v for k, v in headers.items()
    }
    return await firm.net.http.request(method, path, json=body, headers=sent)


async def _new_draft(firm: Firm) -> Body:
    made = await _call(
        firm,
        "POST",
        "/v1/envelopes",
        {"source_kind": KIND, "source_id": str(firm.source_id)},
    )
    assert made.status_code == 201, made.text
    return cast(Body, made.json())


async def _scanned_clean(firm: Firm) -> None:
    """P-03's scan found no TIN on the version's one page."""
    await firm.net.seed.run(
        "INSERT INTO pii_scan_runs (tenant_id, evidence_version_id, detector_version, "
        "pages_scanned, pages_not_scannable, region_count) VALUES ($1, $2, 'd2', '{1}', '{}', 0)",
        firm.tenant_id,
        firm.site.version_id,
    )


async def test_ac_a_signer_without_email_blocks_send_with_409(firm: Firm) -> None:
    draft = await _new_draft(firm)
    envelope = draft["row"]["id"]
    assert draft["row"]["status"] == "draft" and draft["row"]["provider"] == "docusign"
    assert [s["role"] for s in draft["signers"]] == ["signer", "ero"]
    assert draft["signers"][0]["email"] is None
    await _scanned_clean(firm)
    checked = (await _call(firm, "POST", f"/v1/envelopes/{envelope}/validate")).json()
    assert checked["ok"] is False
    sofia_signer = draft["signers"][0]["id"]
    assert f"signer_email_missing:{sofia_signer}" in checked["problems"]
    by_code = {c["code"]: c["ok"] for c in checked["checks"]}
    assert by_code["emails_present"] is False and by_code["ero_present"] is True
    refused = await _call(
        firm, "POST", f"/v1/envelopes/{envelope}/send", Idempotency_Key=uuid.uuid4().hex
    )
    assert refused.status_code == 409
    assert refused.json()["detail"] == "validation_failed"
    assert refused.json()["facts"]["emails_present"] is False
    grants = await firm.net.seed.value(
        "SELECT count(*) FROM approval_grants WHERE subject_id = $1", uuid.UUID(envelope)
    )
    assert grants == 0


async def test_ac_a_send_undone_inside_ten_seconds_makes_no_provider_call(firm: Firm) -> None:
    draft = await _new_draft(firm)
    envelope = uuid.UUID(draft["row"]["id"])
    await firm.net.seed.run(
        "UPDATE contacts SET email = 'sofia@example.com' WHERE id = $1", firm.sofia
    )
    await _scanned_clean(firm)
    key = uuid.uuid4().hex
    sent = await _call(firm, "POST", f"/v1/envelopes/{envelope}/send", Idempotency_Key=key)
    assert sent.status_code == 200, sent.text
    grant = uuid.UUID(sent.json()["grant_id"])
    # The same key answers the same send: one grant.
    again = await _call(firm, "POST", f"/v1/envelopes/{envelope}/send", Idempotency_Key=key)
    assert again.status_code == 200, again.text
    assert again.json()["grant_id"] == str(grant)
    undone = await _call(firm, "POST", f"/v1/envelopes/{envelope}/send/undo")
    assert undone.status_code == 200, undone.text
    seed = firm.net.seed
    row = (await seed.rows("SELECT status, sent_at FROM envelopes WHERE id = $1", envelope))[0]
    assert row["status"] == "draft" and row["sent_at"] is None
    voided = await seed.value("SELECT voided_at FROM approval_grants WHERE id = $1", grant)
    assert voided is not None
    calls = await seed.value(
        "SELECT count(*) FROM envelope_provider_calls WHERE envelope_id = $1", envelope
    )
    assert calls == 0
    kinds = [
        r["kind"]
        for r in await seed.rows(
            "SELECT kind FROM envelope_events WHERE envelope_id = $1 ORDER BY recorded_at",
            envelope,
        )
    ]
    assert kinds == ["envelope.drafted", "envelope.send_requested", "envelope.send_undone"]


async def test_edits_need_the_current_version_and_an_allowed_method(firm: Firm) -> None:
    draft = await _new_draft(firm)
    envelope = draft["row"]["id"]
    version = draft["version"]
    body: Body = {
        "signers": [
            {"order": 1, "contact_id": str(firm.sofia), "identity_method": "kba"},
            {
                "order": 2,
                "user_id": str(firm.ero.user_id),
                "role": "ero",
                "identity_method": "firm_sso",
            },
        ],
        "signer_order": "sequential",
    }
    stale = await _call(firm, "PUT", f"/v1/envelopes/{envelope}", body, If_Match=str(version + 5))
    assert stale.status_code == 409 and stale.json()["detail"] == "stale_version"
    email_code = {**body, "signers": [{**body["signers"][0], "identity_method": "email_code"}]}
    refused = await _call(
        firm, "PUT", f"/v1/envelopes/{envelope}", email_code, If_Match=str(version)
    )
    assert refused.status_code == 422
    assert refused.json()["detail"] == "identity_method_not_allowed"
    # Swap the two signers' positions in one edit (the deferred unique), keeping their ids.
    swapped = {
        **body,
        "signers": [{**body["signers"][1], "order": 1}, {**body["signers"][0], "order": 2}],
    }
    saved = await _call(firm, "PUT", f"/v1/envelopes/{envelope}", swapped, If_Match=str(version))
    assert saved.status_code == 200, saved.text
    after = saved.json()
    assert after["version"] == version + 1
    assert [s["role"] for s in after["signers"]] == ["ero", "signer"]
    assert {s["id"] for s in after["signers"]} == {s["id"] for s in draft["signers"]}
    # Removing the ERO from a draft deletes its row.
    alone = {**body, "signers": [body["signers"][0]]}
    trimmed = await _call(
        firm, "PUT", f"/v1/envelopes/{envelope}", alone, If_Match=str(version + 1)
    )
    assert trimmed.status_code == 200, trimmed.text
    assert len(trimmed.json()["signers"]) == 1
