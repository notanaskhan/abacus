# ac-test-author: ayushkbhatia
"""N-02-T41 (ADR-078; TASK-2534; N-02 §3.3, §3.7, §3.13; Pub 1345; DF-11; I-RETENTION-FLOOR;
C7 v1.1): the independent suite for notanaskhan's red rows N-02-T27, N-02-T28 and N-02-T38,
written from the N-02 epic, C7 v1.1 and Pub 1345 rather than the code.

The row's acceptance: "The suite passes and fails on a fourth remote attempt or a shortened
retain-until." Here:

- Three identity failures close a signer's remote path (`verification_failed`); a fourth attempt
  counts nothing and opens nothing; the e-file policy never allows SMS, and a change that would is
  refused.
- A hand-signed form needs the sender's attestation; on paper too the taxpayer signs before a
  later group (the ERO).
- Reminders are a person's and stop at the policy's cap.
- Each signer's evidence package carries the five IRS items and reads back by its hash.
- Retention only moves forward, at the service and at the database.
- A superseded envelope leaves the e-file gate unmet, and only the system supersedes.

The envelope is N-02-T14's two-signer Form 8879 (Thomas and Irene Kowal), sent by Grace on the
fake provider; the buckets and provider are N-02-T27's fixtures, the legible page N-02-T38's.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import cast

import asyncpg
import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.evidence.records import get_record
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.signatures import activities, countersign
from abacus.modules.signatures.api import (
    EFILE_GATE,
    RetentionNotExtended,
    envelope_gate_facts,
    extend_retention,
)
from abacus.modules.signatures.consumers import SystemOnly, supersede_for_amount_change
from abacus.modules.signatures.imports import RECORD_TYPE
from abacus_tools.fakes.esign import FakeEsign, FakeEsignError

from . import test_n02t14_envelope_workflow as t14
from . import test_n02t27_handwritten_fallback as t27
from .support import Net
from .test_n02t27_handwritten_fallback import fake, raw
from .test_n02t38_evidence_hardening import page

__all__ = ["fake", "page", "raw"]

pytestmark = pytest.mark.asyncio
_out = t27._out  # pyright: ignore[reportPrivateUsage] -- N-02-T27's sent 8879
_irene = t27._irene  # pyright: ignore[reportPrivateUsage] -- N-02-T27's signer read
_wet = t27._wet  # pyright: ignore[reportPrivateUsage] -- N-02-T27's paper upload
FIVE = ("signed_image_sha256", "signed_at", "ip_masked", "login_ref", "identity_result")


def _person_ctx(sent: t14.Sent, kind: str) -> AuthContext:
    return AuthContext(
        TenantContext(sent.tenant_id, kind, str(sent.grace.user_id)),  # type: ignore[arg-type]  # each actor kind
        sent.grace.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


async def _close_irene(sent: t14.Sent, pid: str, fake: FakeEsign) -> None:
    for _ in range(3):
        fake.fail_identity(pid, str(sent.signers[1]))
    await activities.envelope_poll(sent.given)


# --- three failures, no retry, no SMS ----------------------------------------------------------


async def test_three_failures_close_the_remote_path_and_a_fourth_attempt_changes_nothing(
    net: Net, fake: FakeEsign
) -> None:
    sent, pid = await _out(net, fake)
    await _close_irene(sent, pid, fake)
    assert (await _irene(sent))["status"] == "verification_failed"
    # A fourth attempt: the provider may refuse it outright (FakeEsignError), or record it.
    with contextlib.suppress(FakeEsignError):
        fake.fail_identity(pid, str(sent.signers[1]))
    await activities.envelope_poll(sent.given)
    irene = await _irene(sent)
    assert (irene["status"], irene["kba_failures"]) == ("verification_failed", 3)
    issued = await net.seed.value(
        "SELECT count(*) FROM signing_sessions WHERE signer_id = $1 AND state = 'issued'",
        sent.signers[1],
    )
    assert issued == 0
    told = await net.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'envelope.signer_verification_failed'",
        sent.tenant_id,
    )
    assert told == 1  # the sender is told once, not per attempt


async def test_the_efile_policy_never_allows_sms(net: Net, fake: FakeEsign) -> None:
    sent, _pid = await _out(net, fake)
    listed = await net.call("GET", "/v1/envelope-policies", sent.grace)
    assert listed.status_code == 200, listed.text
    efile = next(p for p in listed.json() if p["policy_family"] == "efile_authorization")
    assert "sms" not in efile["allowed_identity_methods"]
    security = await net.seed.person(sent.tenant_id, "security_admin")
    with_sms = {
        "allowed_identity_methods": ["kba", "sms"],
        "default_identity_method": "kba",
        "kba_max_attempts": efile["kba_max_attempts"],
        "max_reminders": efile["max_reminders"],
        "default_expiry_days": efile["default_expiry_days"],
        "countersign_required": efile["countersign_required"],
        "version": efile["version"],
    }
    refused = await net.call(
        "PUT", "/v1/envelope-policies/efile_authorization", security, body=with_sms
    )
    assert refused.status_code in (409, 422), refused.text


# --- paper: attestation and order --------------------------------------------------------------


async def test_a_hand_signed_form_needs_the_senders_attestation(net: Net, fake: FakeEsign) -> None:
    sent, pid = await _out(net, fake)
    await _close_irene(sent, pid, fake)
    who = net.headers(sent.grace)
    staged = await net.http.post(
        "/v1/envelopes/import/files",
        params={
            "filename": "kowal-8879-irene.pdf",
            "client_id": str(sent.site.client_id),
            "engagement_id": str(sent.site.engagement_id),
        },
        content=t27.SCAN,
        headers={**who, "Content-Type": "application/octet-stream"},
    )
    assert staged.status_code == 201, staged.text
    unattested = await net.http.post(
        f"/v1/envelopes/{sent.envelope_id}/signers/{sent.signers[1]}/wet-signature",
        json={
            "upload_id": staged.json()["id"],
            "signed_on": "2026-09-11",
            "attested": False,
            "received_on": "2026-09-12",
        },
        headers={**who, "Idempotency-Key": "n02t41-unattested"},
    )
    assert unattested.status_code in (409, 422), unattested.text
    assert (await _irene(sent))["status"] == "verification_failed"


async def test_on_paper_too_the_earlier_group_signs_first(net: Net, fake: FakeEsign) -> None:
    sent, pid = await _out(net, fake)
    # Irene signs after Thomas (a later group, as the ERO signs after the taxpayer).
    await net.seed.run(
        "UPDATE envelope_signers SET routing_group = 2 WHERE id = $1", sent.signers[1]
    )
    await _close_irene(sent, pid, fake)
    assert await _wet(sent, net.headers(sent.grace), "n02t41-early") == 409
    fake.sign(pid, str(sent.signers[0]), ip=t14.IP)
    await activities.envelope_poll(sent.given)
    assert await _wet(sent, net.headers(sent.grace), "n02t41-in-turn") == 200


# --- reminders -----------------------------------------------------------------------------------


async def test_reminders_are_a_persons_and_stop_at_the_cap(net: Net, fake: FakeEsign) -> None:
    sent, _pid = await _out(net, fake)
    for kind in ("agent", "system"):
        with pytest.raises(Forbidden):
            await countersign.remind_preview(_person_ctx(sent, kind), [sent.envelope_id])
    preview = await net.call(
        "POST",
        "/v1/envelopes/remind/preview",
        sent.grace,
        body={"envelope_ids": [str(sent.envelope_id)]},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["count"] >= 1
    listed = await net.call("GET", "/v1/envelope-policies", sent.grace)
    efile = next(p for p in listed.json() if p["policy_family"] == "efile_authorization")
    cap = int(efile["max_reminders"])
    for _ in range(cap):
        await net.seed.run(
            "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, occurred_at) "
            "VALUES ($1, $2, 'envelope.reminded', 'firm', now())",
            sent.tenant_id,
            sent.envelope_id,
        )
    capped = await net.call(
        "POST",
        "/v1/envelopes/remind/preview",
        sent.grace,
        body={"envelope_ids": [str(sent.envelope_id)]},
    )
    assert capped.status_code == 200, capped.text
    assert (capped.json()["count"], capped.json()["skipped"]) == (0, [str(sent.envelope_id)])


# --- the evidence package, retention and the gate ----------------------------------------------


async def _completed(net: Net, fake: FakeEsign) -> t14.Sent:
    sent, pid = await _out(net, fake)
    for signer in sent.signers:
        fake.sign(pid, str(signer), ip=t14.IP)
    assert await activities.envelope_poll(sent.given) == "completed"
    assert await activities.envelope_complete(sent.given) == "recorded"
    return sent


async def test_each_package_carries_the_five_irs_items_and_reads_back_by_its_hash(
    net: Net, fake: FakeEsign, page: list[object]
) -> None:
    sent = await _completed(net, fake)
    rows = await net.seed.rows(
        "SELECT signer_id, package_sha256, signature_method FROM signature_evidence "
        "WHERE envelope_id = $1",
        sent.envelope_id,
    )
    assert {r["signer_id"] for r in rows} == set(sent.signers)
    for row in rows:
        digest = cast(str, row["package_sha256"])
        body = await get_record(sent.tenant_id, RECORD_TYPE, digest)
        assert body is not None
        assert hashlib.sha256(body).hexdigest() == digest.removeprefix("sha256:")
        text = body.decode()
        for item in (*FIVE, "signature_method"):
            assert item in text, item
        assert t14.IP not in text  # the full address is sealed, never in a package
        json.loads(body)


async def test_retention_only_moves_forward_at_the_service_and_the_database(
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
    later = held + timedelta(days=30)
    assert await extend_retention(system, sent.envelope_id, later) == later
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await net.seed.run(
            "UPDATE envelopes SET retain_until = $2 WHERE id = $1",
            sent.envelope_id,
            later - timedelta(days=1),
        )
    assert (
        await net.seed.value("SELECT retain_until FROM envelopes WHERE id = $1", sent.envelope_id)
        == later
    )


async def test_a_superseded_envelope_leaves_the_efile_gate_unmet(
    net: Net, fake: FakeEsign, page: list[object]
) -> None:
    sent = await _completed(net, fake)
    tax_return = uuid.uuid4()
    await net.seed.run(
        "UPDATE envelopes SET source_kind = 'tax_return', source_id = $2 WHERE id = $1",
        sent.envelope_id,
        tax_return,
    )
    reader = _person_ctx(sent, "human")
    assert (await envelope_gate_facts(reader, EFILE_GATE, tax_return)).met is True
    with pytest.raises(SystemOnly):
        await supersede_for_amount_change(reader.tenant, sent.envelope_id, "binding-v2")
    system = TenantContext(sent.tenant_id, "system", "tax:binding")
    assert await supersede_for_amount_change(system, sent.envelope_id, "binding-v2") is True
    facts = await envelope_gate_facts(reader, EFILE_GATE, tax_return)
    assert (facts.met, facts.envelope_id) == (False, None)
    assert (
        await net.seed.value("SELECT status FROM envelopes WHERE id = $1", sent.envelope_id)
        == "completed"
    )
