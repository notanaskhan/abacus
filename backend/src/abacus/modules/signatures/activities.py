"""EnvelopeWorkflow's activities (N-02-T14; N-02 §3.3, §3.5, §3.7; ADR-004, ADR-149; DEC-74).

Each runs as the system for one envelope (`envelope:<envelope>`), in its own unit of work with
its audit event, and is safe to retry:

- `envelope_send`: the provider creates and sends once (its idempotency key is the envelope's;
  the call is recorded write-once in `envelope_provider_calls`), the recipients are mapped, the
  expiry set from the policy when the person left it open; returns the reminder plan.
- `envelope_poll`: the provider's signer states (the truth), each change recorded as an
  `envelope_events` row from `provider_poll`; the envelope's status follows (sent, viewed,
  partially signed, declined, completed) and never moves back.
- `envelope_remind`: one due reminder to the signers still to sign in the current routing
  group, under the policy cap, through the human-approved template (`reminders.py`).
- `envelope_expire`: an open envelope past `expires_at` becomes Expired; the provider envelope
  is voided and issued signing sessions are abandoned.
- `envelope_complete`: one evidence package per signer (the five IRS items: the signed image,
  the date and time, the IP address and login ID, the identity result and the method) and one
  manifest, written to the records bucket in COMPLIANCE mode until the retention floor; the
  `signature_evidence` rows; the signed copy filed under Signed authorizations; one
  `envelope.completed`. The full address is kept sealed (`hub.seal_ip`), never in a package.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import service_line_of
from abacus.modules.evidence.api import (
    file_signed_copy,
    put_record,
    retain_until_for,
    screen_and_stage,
)
from abacus.modules.identity.api import firm_time_zone
from abacus.modules.signatures.events import EnvelopeCompleted
from abacus.modules.signatures.hub import seal_ip
from abacus.modules.signatures.imports import RECORD_TYPE, RetentionFloorMissing
from abacus.modules.signatures.provider import (
    EnvelopeSpec,
    ProviderUnavailable,
    SignerSpec,
    SignerState,
    provider_for,
)
from abacus.modules.signatures.reminders import reminder_instants, reminder_sender
from abacus.modules.signatures.workflows import EnvelopeInput, ReminderDue, SendPlan

OPEN: Final = ("sent", "viewed", "partially_signed")
DEFAULT_EXPIRY_DAYS: Final = 30
DEFAULT_CAP: Final = 3
# How far each envelope status is along; the poll never moves an envelope back.
_RANK: Final = {"sent": 0, "viewed": 1, "partially_signed": 2, "declined": 3, "completed": 3}


def _system(tenant_id: str, envelope_id: str) -> TenantContext:
    return TenantContext(UUID(tenant_id), "system", f"envelope:{envelope_id}")


def mask_ip(ip: str) -> str:
    """`73.44.•••.•••` for IPv4; the first two groups for IPv6."""
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return "•••"
    if parsed.version == 4:
        a, b, _c, _d = ip.split(".")
        return f"{a}.{b}.•••.•••"
    groups = parsed.exploded.split(":")
    return f"{groups[0]}:{groups[1]}:•••"


_ENVELOPE = text(
    "SELECT id, status, provider, provider_envelope_id, policy_family, purpose, "
    "reminder_cadence, expires_at, sent_at, client_id, engagement_id, work_item_id, title, "
    "source_kind, source_id, completed_at FROM envelopes WHERE id = :id"
)
_POLICY = text(
    "SELECT max_reminders, default_expiry_days FROM envelope_policies "
    "WHERE policy_family = :family AND (purpose = :purpose OR purpose IS NULL) "
    "ORDER BY purpose NULLS LAST LIMIT 1"
)
_SIGNERS = text(
    'SELECT id, "order", routing_group, identity_method, status, viewed_at, signed_at, '
    "kba_failures, decline_reason, provider_recipient_id FROM envelope_signers "
    'WHERE envelope_id = :id ORDER BY "order"'
)
_EVENT = text(
    "INSERT INTO envelope_events (tenant_id, envelope_id, signer_id, kind, source, occurred_at) "
    "VALUES (:tenant, :envelope, :signer, :kind, :source, :at)"
)


async def _policy(tenant: TenantContext, family: str, purpose: str) -> tuple[int, int]:
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(_POLICY, {"family": family, "purpose": purpose})
        ).one_or_none()
    if found is None:
        return DEFAULT_CAP, DEFAULT_EXPIRY_DAYS
    return int(found.max_reminders), int(found.default_expiry_days)


@activity.defn(name="signatures.envelope_send")
async def envelope_send(given: EnvelopeInput) -> SendPlan:
    tenant = _system(given.tenant_id, given.envelope_id)
    envelope_id = UUID(given.envelope_id)
    async with tenant_session(tenant) as session:
        env = (await session.execute(_ENVELOPE, {"id": envelope_id})).one_or_none()
        people = (await session.execute(_SIGNERS, {"id": envelope_id})).all()
        docs = (
            await session.execute(
                text(
                    "SELECT sha256 FROM envelope_documents WHERE envelope_id = :id "
                    'ORDER BY "order"'
                ),
                {"id": envelope_id},
            )
        ).scalars()
        hashes = tuple(str(d) for d in docs)
    if env is None or env.provider == "record" or env.sent_at is None:
        return SendPlan("not_sent", "")
    if env.status not in OPEN:
        return SendPlan(str(env.status), "")
    cap, expiry_days = await _policy(tenant, env.policy_family, env.purpose)
    expires: datetime = env.expires_at or env.sent_at + timedelta(days=expiry_days)
    if env.provider_envelope_id is None:
        spec = EnvelopeSpec(
            envelope_id=given.envelope_id,
            idempotency_key=f"envelope:{given.envelope_id}",
            document_sha256s=hashes,
            signers=tuple(
                SignerSpec(str(p.id), int(p.order), int(p.routing_group), p.identity_method)
                for p in people
            ),
        )
        try:
            adapter = await provider_for(tenant.tenant_id)
        except ProviderUnavailable:
            # The kill switch, W7 or the firm's install is off: recorded, nothing leaves.
            async with uow(tenant) as tx:
                await tx.session.execute(
                    _EVENT,
                    {
                        "tenant": tenant.tenant_id,
                        "envelope": envelope_id,
                        "signer": None,
                        "kind": "envelope.provider_unavailable",
                        "source": "system",
                        "at": system_now(),
                    },
                )
                tx.record("envelope.provider_unavailable", target=Target("envelope", envelope_id))
            return SendPlan("not_sent", "")
        made = await adapter.create_and_send(spec)
        request = hashlib.sha256(json.dumps(asdict(spec), sort_keys=True).encode()).hexdigest()
        now = system_now()
        async with uow(tenant) as tx:
            await tx.session.execute(
                text(
                    "INSERT INTO envelope_provider_calls (tenant_id, envelope_id, operation, "
                    "idempotency_key, request_sha256, response_sha256, status_code) VALUES "
                    "(:tenant, :envelope, 'create_envelope', :key, :request, :response, 201) "
                    "ON CONFLICT (tenant_id, operation, idempotency_key) DO NOTHING"
                ),
                {
                    "tenant": tenant.tenant_id,
                    "envelope": envelope_id,
                    "key": spec.idempotency_key,
                    "request": request,
                    "response": made.response_sha256,
                },
            )
            await tx.session.execute(
                text(
                    "UPDATE envelopes SET provider_envelope_id = :pid, expires_at = :expires, "
                    "version = version + 1, updated_at = :now "
                    "WHERE id = :id AND provider_envelope_id IS NULL"
                ),
                {
                    "pid": made.provider_envelope_id,
                    "expires": expires,
                    "now": now,
                    "id": envelope_id,
                },
            )
            for signer, recipient in made.recipients.items():
                await tx.session.execute(
                    text(
                        "UPDATE envelope_signers SET provider_recipient_id = :recipient "
                        "WHERE id = :id AND envelope_id = :envelope"
                    ),
                    {"recipient": recipient, "id": UUID(signer), "envelope": envelope_id},
                )
            await tx.session.execute(
                _EVENT,
                {
                    "tenant": tenant.tenant_id,
                    "envelope": envelope_id,
                    "signer": None,
                    "kind": "envelope.provider_sent",
                    "source": "system",
                    "at": now,
                },
            )
            tx.record(
                "envelope.provider_sent",
                target=Target("envelope", envelope_id),
                after=Ref(response_sha256=made.response_sha256),
            )
    zone = await firm_time_zone(tenant)
    reminders = reminder_instants(
        cadence=env.reminder_cadence, sent_at=env.sent_at, expires_at=expires, cap=cap, zone=zone
    )
    return SendPlan("sent", expires.isoformat(), [r.isoformat() for r in reminders])


def _envelope_status(states: list[tuple[str, int]]) -> str:
    """The envelope's status from its signers' (status, routing group)."""
    codes = [s for s, _g in states]
    if codes and all(c == "signed" for c in codes):
        return "completed"
    if "declined" in codes:
        return "declined"
    if "signed" in codes:
        return "partially_signed"
    if "viewed" in codes or "verification_failed" in codes:
        return "viewed"
    return "sent"


@activity.defn(name="signatures.envelope_poll")
async def envelope_poll(given: EnvelopeInput) -> str:
    tenant = _system(given.tenant_id, given.envelope_id)
    envelope_id = UUID(given.envelope_id)
    async with tenant_session(tenant) as session:
        env = (await session.execute(_ENVELOPE, {"id": envelope_id})).one()
        people = {p.id: p for p in (await session.execute(_SIGNERS, {"id": envelope_id})).all()}
    if env.status not in OPEN or env.provider_envelope_id is None:
        return str(env.status)
    states: dict[UUID, SignerState] = {
        UUID(s.signer_id): s
        for s in await (await provider_for(tenant.tenant_id)).status(env.provider_envelope_id)
    }
    now = system_now()
    after: list[tuple[str, int]] = []
    changed: list[tuple[UUID, str]] = []
    for signer_id, row in people.items():
        state = states.get(signer_id)
        status = row.status if state is None else state.status
        after.append((status, int(row.routing_group)))
        if state is not None and state.status != row.status:
            changed.append((signer_id, state.status))
    status = _envelope_status(after)
    if _RANK.get(status, 0) < _RANK.get(str(env.status), 0):
        status = str(env.status)
    if not changed and status == env.status:
        return status
    async with uow(tenant) as tx:
        for signer_id, code in changed:
            state = states[signer_id]
            await tx.session.execute(
                text(
                    "UPDATE envelope_signers SET status = :status, viewed_at = COALESCE("
                    "viewed_at, :viewed), signed_at = :signed, kba_failures = :kba, "
                    "decline_reason = :reason, signature_method = CASE WHEN :status = "
                    "'signed' THEN COALESCE(signature_method, 'provider_adopted') ELSE "
                    "signature_method END WHERE id = :id"
                ),
                {
                    "status": code,
                    "viewed": state.viewed_at,
                    "signed": state.signed_at,
                    "kba": state.kba_failures,
                    "reason": state.decline_reason,
                    "id": signer_id,
                },
            )
            await tx.session.execute(
                _EVENT,
                {
                    "tenant": tenant.tenant_id,
                    "envelope": envelope_id,
                    "signer": signer_id,
                    "kind": f"signer.{code}",
                    "source": "provider_poll",
                    "at": now,
                },
            )
        if status != env.status:
            await tx.session.execute(
                text(
                    "UPDATE envelopes SET status = :status, completed_at = CASE WHEN :status = "
                    "'completed' THEN :now ELSE completed_at END, version = version + 1, "
                    "updated_at = :now WHERE id = :id"
                ),
                {"status": status, "now": now, "id": envelope_id},
            )
            await tx.session.execute(
                _EVENT,
                {
                    "tenant": tenant.tenant_id,
                    "envelope": envelope_id,
                    "signer": None,
                    "kind": f"envelope.{status}",
                    "source": "provider_poll",
                    "at": now,
                },
            )
        tx.record(
            "envelope.polled",
            target=Target("envelope", envelope_id),
            after=Ref(changed=len(changed)),
        )
    return status


@activity.defn(name="signatures.envelope_remind")
async def envelope_remind(given: ReminderDue) -> str:
    tenant = _system(given.tenant_id, given.envelope_id)
    envelope_id = UUID(given.envelope_id)
    async with tenant_session(tenant) as session:
        env = (await session.execute(_ENVELOPE, {"id": envelope_id})).one()
        people = (await session.execute(_SIGNERS, {"id": envelope_id})).all()
        sent = int(
            (
                await session.execute(
                    text(
                        "SELECT count(*) FROM envelope_events WHERE envelope_id = :id "
                        "AND kind = 'envelope.reminded'"
                    ),
                    {"id": envelope_id},
                )
            ).scalar_one()
        )
    if env.status not in OPEN or system_now() >= (env.expires_at or system_now()):
        return "closed"
    cap, _expiry = await _policy(tenant, env.policy_family, env.purpose)
    if sent >= cap:
        return "capped"
    waiting = [p for p in people if p.status in ("pending", "viewed")]
    group = min((int(p.routing_group) for p in waiting), default=None)
    targets = [p.id for p in waiting if int(p.routing_group) == group]
    sender = reminder_sender()
    outcome = "skipped" if sender is None or not targets else "sent"
    if sender is not None:
        queued = [await sender(tenant, envelope_id, signer, given.sequence) for signer in targets]
        outcome = "sent" if any(queued) else "skipped"
    async with uow(tenant) as tx:
        await tx.session.execute(
            _EVENT,
            {
                "tenant": tenant.tenant_id,
                "envelope": envelope_id,
                "signer": None,
                "kind": "envelope.reminded" if outcome == "sent" else "envelope.reminder_skipped",
                "source": "system",
                "at": system_now(),
            },
        )
        tx.record(
            "envelope.reminded" if outcome == "sent" else "envelope.reminder_skipped",
            target=Target("envelope", envelope_id),
            after=Ref(sequence=given.sequence, signers=len(targets)),
        )
    return outcome


@activity.defn(name="signatures.envelope_expire")
async def envelope_expire(given: EnvelopeInput) -> str:
    tenant = _system(given.tenant_id, given.envelope_id)
    envelope_id = UUID(given.envelope_id)
    async with tenant_session(tenant) as session:
        env = (await session.execute(_ENVELOPE, {"id": envelope_id})).one()
    if env.status not in OPEN:
        return str(env.status)
    if env.provider_envelope_id is not None:
        await (await provider_for(tenant.tenant_id)).void(env.provider_envelope_id, "expired")
    now = system_now()
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE envelopes SET status = 'expired', version = version + 1, "
                "updated_at = :now WHERE id = :id AND status = ANY(:open)"
            ),
            {"now": now, "id": envelope_id, "open": list(OPEN)},
        )
        await tx.session.execute(
            text(
                "UPDATE signing_sessions SET state = 'abandoned' "
                "WHERE envelope_id = :id AND state = 'issued'"
            ),
            {"id": envelope_id},
        )
        await tx.session.execute(
            _EVENT,
            {
                "tenant": tenant.tenant_id,
                "envelope": envelope_id,
                "signer": None,
                "kind": "envelope.expired",
                "source": "system",
                "at": now,
            },
        )
        tx.record("envelope.expired", target=Target("envelope", envelope_id))
    return "expired"


def _package(
    header: dict[str, str],
    signer_id: str,
    evidence: dict[str, object],
    documents: list[str],
) -> bytes:
    return json.dumps(
        {
            **header,
            "signer_id": signer_id,
            "document_sha256s": documents,
            **evidence,
        },
        sort_keys=True,
    ).encode()


@activity.defn(name="signatures.envelope_complete")
async def envelope_complete(given: EnvelopeInput) -> str:
    tenant = _system(given.tenant_id, given.envelope_id)
    envelope_id = UUID(given.envelope_id)
    async with tenant_session(tenant) as session:
        env = (await session.execute(_ENVELOPE, {"id": envelope_id})).one()
        recorded = int(
            (
                await session.execute(
                    text("SELECT count(*) FROM signature_evidence WHERE envelope_id = :id"),
                    {"id": envelope_id},
                )
            ).scalar_one()
        )
    if env.status != "completed" or env.provider_envelope_id is None:
        return str(env.status)
    if recorded:
        return "recorded"  # a retry after the unit of work committed
    got = await (await provider_for(tenant.tenant_id)).completed(env.provider_envelope_id)
    line = (
        await service_line_of(tenant, env.engagement_id) if env.engagement_id is not None else None
    ) or "any"
    completed_at: datetime = env.completed_at or system_now()
    keep = await retain_until_for(tenant, RECORD_TYPE, line, completed_at)
    if keep is None:
        raise RetentionFloorMissing
    document = await put_record(tenant.tenant_id, RECORD_TYPE, got.combined_document, keep)
    certificate = await put_record(tenant.tenant_id, RECORD_TYPE, got.certificate, keep)
    documents = [document.sha256, certificate.sha256]
    rows: list[dict[str, object]] = []
    packages: list[str] = []
    for item in got.signers:
        image = await put_record(tenant.tenant_id, RECORD_TYPE, item.signed_image, keep)
        sealed = await seal_ip(tenant.tenant_id, UUID(item.signer_id), item.ip)
        masked = mask_ip(item.ip)
        body = _package(
            {
                "envelope_id": given.envelope_id,
                "provider": str(env.provider),
                "provider_envelope_id": str(env.provider_envelope_id),
                "purpose": str(env.purpose),
            },
            item.signer_id,
            {
                "signed_image_sha256": image.sha256,
                "signed_at": item.signed_at.isoformat(),
                "ip_masked": masked,
                "ip_sealed": base64.b64encode(sealed).decode(),
                "login_ref": item.login_ref,
                "identity_result": item.identity_result,
                "signature_method": item.signature_method,
                "user_agent_family": item.user_agent_family,
                "device_label": item.device_label,
            },
            documents,
        )
        package = await put_record(tenant.tenant_id, RECORD_TYPE, body, keep)
        packages.append(package.sha256)
        rows.append(
            {
                "tenant": tenant.tenant_id,
                "envelope": envelope_id,
                "signer": UUID(item.signer_id),
                "signed_at": item.signed_at,
                "sealed": sealed,
                "masked": masked,
                "login": item.login_ref,
                "agent": item.user_agent_family,
                "device": item.device_label,
                "result": item.identity_result,
                "method": item.signature_method,
                "image": image.key,
                "hashes": documents,
                "key": package.key,
                "sha": package.sha256,
                "keep": keep.date(),
            }
        )
    manifest = json.dumps(
        {"envelope_id": given.envelope_id, "documents": documents, "packages": packages},
        sort_keys=True,
    ).encode()
    stored_manifest = await put_record(tenant.tenant_id, RECORD_TYPE, manifest, keep)
    screened = await screen_and_stage(
        tenant.tenant_id, got.combined_document, f"{env.title}.pdf", None
    )
    async with uow(tenant) as tx:
        for row in rows:
            await tx.session.execute(
                text(
                    "INSERT INTO signature_evidence (tenant_id, envelope_id, signer_id, "
                    "signed_at, ip_sealed, ip_masked, login_ref, user_agent_family, "
                    "device_label, identity_result, signature_method, signed_image_key, "
                    "document_sha256s, package_key, package_sha256, retain_until) VALUES "
                    "(:tenant, :envelope, :signer, :signed_at, :sealed, :masked, :login, "
                    ":agent, :device, :result, :method, :image, :hashes, :key, :sha, :keep)"
                ),
                row,
            )
        await file_signed_copy(
            tx,
            tenant_id=tenant.tenant_id,
            client_id=env.client_id,
            engagement_id=env.engagement_id,
            work_item_id=env.work_item_id,
            title=env.title,
            stored_key=screened.stored.key,
            stored_version_id=screened.stored.version_id,
            sha256=screened.sha256,
            size_bytes=screened.stored.size,
            media_type=screened.media_type,
            actor_kind=tenant.actor_kind,
            actor_id=tenant.actor_id,
        )
        await tx.session.execute(
            _EVENT,
            {
                "tenant": tenant.tenant_id,
                "envelope": envelope_id,
                "signer": None,
                "kind": "envelope.evidence_recorded",
                "source": "system",
                "at": system_now(),
            },
        )
        tx.record(
            "envelope.evidence_recorded",
            target=Target("envelope", envelope_id),
            after=Ref(manifest_sha256=stored_manifest.sha256, signers=len(rows)),
        )
        tx.emit(
            EnvelopeCompleted(
                envelope_id=envelope_id,
                client_id=env.client_id,
                engagement_id=env.engagement_id,
                purpose=env.purpose,
                provider=env.provider,
                source_kind=env.source_kind or "envelope",
                source_id=env.source_id or envelope_id,
                imported_by=None,
            )
        )
    return "recorded"


ACTIVITIES: Final = (
    envelope_send,
    envelope_poll,
    envelope_remind,
    envelope_expire,
    envelope_complete,
)
