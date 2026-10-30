"""Provider status truth by polling (N-02-T19; N-02 §3.5, §4.6; ADR-152's fallback; DEC-1180).

ADR-152's amendment that would mount `POST /v1/webhooks/docusign-connect` is proposed, not
accepted, so it binds nothing and no unauthenticated route exists: N-02 runs poll-only, as the
amendment's "if refused" clause says.

- **EnvelopeStatusPoll** (Schedule `envelope_status_poll:platform`, every 5 minutes, overlap
  SKIP): for each firm with `signatures.esign_provider` on, every open envelope that DocuSeal
  holds (ADR-342) gets a `provider_hint` signal; its EnvelopeWorkflow runs
  `signatures.envelope_poll`, which reads the provider and records what changed
  (`source = provider_poll`). A hint carries nothing.
- **A portal return** (POR-06, N-02-T24) calls `hint_envelope` for the envelope just signed.
- **Connect (DocuSign's, kept until the N-02-T19 rework retargets or removes it; ADR-342), when
  ADR-152 is accepted:** `verify_connect` checks DocuSign's HMAC (constant time; any configured
  key may match, so keys rotate) and `connect_event` reads only the envelope id
  and the event id from the body; `record_connect_hint` records the event once per provider event
  id (`envelope_events.provider_event_id` is unique per firm) and signals the workflow. The body
  is never trusted for state and never logged.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel._flags import SIGNATURES_ESIGN_PROVIDER
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import PlatformSchedule, signal_with_start
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.identity.api import firm_tenant_ids
from abacus.modules.signatures.workflows import (
    STATUS_POLL_ID,
    EnvelopeInput,
    EnvelopeStatusPollWorkflow,
    EnvelopeWorkflow,
    envelope_workflow_id,
)

POLL_EVERY: Final = timedelta(minutes=5)
_OPEN_AT_PROVIDER: Final = text(
    "SELECT id FROM envelopes WHERE provider = 'docuseal' AND provider_envelope_id IS NOT NULL "
    "AND status IN ('sent', 'viewed', 'partially_signed')"
)
_log = get_logger(__name__)


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "signatures.status_poll")


async def hint_envelope(tenant_id: UUID, envelope_id: UUID) -> None:
    """Ask the envelope's workflow to read the provider now (a poll tick, a portal return or a
    verified Connect call); it starts the workflow if none is running (self-healing)."""
    await signal_with_start(
        EnvelopeWorkflow,
        EnvelopeInput(str(tenant_id), str(envelope_id)),
        id=envelope_workflow_id(str(tenant_id), str(envelope_id)),
        signal="provider_hint",
        payload=None,
    )


@activity.defn(name="signatures.status_poll_sweep")
async def status_poll_sweep() -> int:
    """One tick: a hint per open DocuSeal envelope of each firm with the provider on."""
    hinted = 0
    for tenant_id in await firm_tenant_ids():
        tenant = _system(tenant_id)
        try:
            if not await flag_enabled(tenant, SIGNATURES_ESIGN_PROVIDER):
                continue
            async with tenant_session(tenant) as session:
                ids = list((await session.execute(_OPEN_AT_PROVIDER)).scalars())
            for envelope_id in ids:
                await hint_envelope(tenant_id, envelope_id)
                hinted += 1
        except Exception as exc:  # one firm's failure never stops the others
            _log.error("status_poll.failed", tenant_id=str(tenant_id), error=type(exc).__name__)
    return hinted


# --- DocuSign Connect (mounted only once ADR-152's amendment is accepted) ----------------------


@dataclass(frozen=True)
class ConnectEvent:
    provider_envelope_id: str
    event_id: str


def verify_connect(body: bytes, signatures: Sequence[str], keys: Sequence[bytes]) -> bool:
    """DocuSign's Connect HMAC: base64(HMAC-SHA256(key, body)) in `X-DocuSign-Signature-n`. True
    only if some configured key matches some signature, compared in constant time."""
    if not body or not signatures or not keys:
        return False
    expected = [base64.b64encode(hmac.new(k, body, hashlib.sha256).digest()) for k in keys]
    matched = False
    for given in signatures:
        raw = given.strip().encode()
        for want in expected:
            matched |= hmac.compare_digest(raw, want)
    return matched


def connect_event(body: bytes) -> ConnectEvent | None:
    """The envelope id and the event id, and nothing else; None for a body without them."""
    try:
        parsed = cast(dict[str, object], json.loads(body))
    except (ValueError, UnicodeDecodeError):
        return None
    data = parsed.get("data")
    envelope = cast(dict[str, object], data).get("envelopeId") if isinstance(data, dict) else None
    event = parsed.get("generatedDateTime") or parsed.get("eventId")
    if not isinstance(envelope, str) or not envelope or not isinstance(event, str):
        return None
    digest = hashlib.sha256(f"{envelope}:{parsed.get('event')}:{event}".encode()).hexdigest()
    return ConnectEvent(envelope[:200], digest)


async def record_connect_hint(tenant_id: UUID, envelope_id: UUID, event: ConnectEvent) -> bool:
    """Record the hint once per provider event id and signal the workflow; False for a
    duplicate (recorded once, nothing signalled again). Changes no envelope state."""
    tenant = _system(tenant_id)
    async with uow(tenant) as tx:
        added = (
            await tx.session.execute(
                text(
                    "INSERT INTO envelope_events (tenant_id, envelope_id, kind, source, "
                    "provider_event_id, occurred_at) VALUES (:tenant, :id, "
                    "'envelope.provider_hint', 'provider_webhook', :event, :now) "
                    "ON CONFLICT (tenant_id, provider_event_id) "
                    "WHERE provider_event_id IS NOT NULL DO NOTHING RETURNING id"
                ),
                {
                    "tenant": tenant_id,
                    "id": envelope_id,
                    "event": event.event_id,
                    "now": system_now(),
                },
            )
        ).first() is not None
        tx.record(
            "envelope.provider_hint",
            target=Target("envelope", envelope_id),
            after=Ref(duplicate=0 if added else 1),
        )
    if added:
        await hint_envelope(tenant_id, envelope_id)
    return added


SCHEDULES: tuple[PlatformSchedule, ...] = (
    PlatformSchedule(
        id=STATUS_POLL_ID,
        workflow=EnvelopeStatusPollWorkflow,
        every=POLL_EVERY,
        note="N-02-T19: hint each open DocuSeal envelope's workflow to read the provider",
    ),
)
ACTIVITIES: tuple[object, ...] = (status_poll_sweep,)
