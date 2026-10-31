"""The DocuSeal webhook receiver (ADR-152 accepted with its amendment, 2026-10-30; ADR-342,
ADR-041; DEC-1281). `POST /v1/webhooks/docuseal/{tenant_id}/{install_id}`, no principal.

A delivery is a hint, never state. In order, and nothing is written before the signature holds:

1. A body over `MAX_BODY_BYTES` is refused (413); a delivery with no signature header is refused
   (401) before anything is looked up.
2. The firm's install: integrations' answer through the slot the API fills
   (`register_esign_webhook`; signatures may not import integrations, ADR-008): the opened secret
   of exactly this install, only with W7 open and the install connected. None, or no webhook key
   in it, or the firm's `signatures.esign_provider` kill switch off: 401.
3. `status_poll.verify_webhook`: DocuSeal's `X-Docuseal-Signature` against every key the install
   holds (rotation), within the replay tolerance. Fails: 401 and a metric only.
4. `status_poll.webhook_event`: the submission id and a stable event id, nothing else. A body
   without them, or a submission this firm has no open DocuSeal envelope for, is acknowledged
   (202) and dropped.
5. At most `HINTS_PER_MINUTE` hints per envelope; beyond that, dropped (the poll still runs).
6. `record_provider_hint`: recorded once per provider event id and the envelope's workflow
   signalled; its poll reads DocuSeal and decides.

Every answer has an empty body; the body and the header are never logged. The per-source limit
is the edge's (the WAF rate rule on `/v1/webhooks/`, Q-01).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import SIGNATURES_ESIGN_PROVIDER
from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import flag_enabled
from abacus.kernel.metrics import meter
from abacus.modules.signatures.docuseal import DocuSealAccount
from abacus.modules.signatures.status_poll import (
    record_provider_hint,
    verify_webhook,
    webhook_event,
)

MAX_BODY_BYTES: Final = 256 * 1024
HINTS_PER_MINUTE: Final = 10
ACCEPTED: Final = 202
REFUSED: Final = 401
TOO_LARGE: Final = 413

# The opened secret of exactly this install (W7 open, install connected), or None.
WebhookSecret = Callable[[TenantContext, UUID], Awaitable[bytes | None]]
_webhook_secret: WebhookSecret | None = None

_refused = meter(__name__).create_counter(
    "abacus.signatures.webhook_refused",
    unit="{delivery}",
    description="DocuSeal webhook deliveries refused before any write, by reason.",
)
_ENVELOPE: Final = text(
    "SELECT id FROM envelopes WHERE provider = 'docuseal' AND provider_envelope_id = :submission "
    "AND status IN ('sent', 'viewed', 'partially_signed')"
)
_RECENT: Final = text(
    "SELECT count(*) FROM envelope_events WHERE envelope_id = :id "
    "AND kind = 'envelope.provider_hint' AND occurred_at > :since"
)


def register_esign_webhook(source: WebhookSecret | None) -> None:
    global _webhook_secret
    _webhook_secret = source


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "signatures.webhook")


def _refuse(reason: str) -> int:
    _refused.add(1, {"reason": reason})
    return REFUSED


async def receive_docuseal_webhook(
    tenant_id: UUID, install_id: UUID, body: bytes, signature: str | None, now: float
) -> int:
    """The HTTP status to answer; see the module docstring for the order."""
    if len(body) > MAX_BODY_BYTES:
        _refused.add(1, {"reason": "too_large"})
        return TOO_LARGE
    if not signature or "." not in signature:
        return _refuse("signature")
    tenant = _system(tenant_id)
    if _webhook_secret is None:
        return _refuse("not_configured")
    raw = await _webhook_secret(tenant, install_id)
    if raw is None:
        return _refuse("no_install")
    keys = DocuSealAccount.from_secret(raw).webhook_keys
    if not keys or not await flag_enabled(tenant, SIGNATURES_ESIGN_PROVIDER):
        return _refuse("not_enabled")
    if not verify_webhook(body, signature, [k.encode() for k in keys], now):
        return _refuse("signature")
    event = webhook_event(body)
    if event is None:
        return ACCEPTED
    async with tenant_session(tenant) as session:
        envelope = await session.scalar(_ENVELOPE, {"submission": event.provider_envelope_id})
        if envelope is None:
            return ACCEPTED
        recent = await session.scalar(
            _RECENT, {"id": envelope, "since": system_now() - timedelta(minutes=1)}
        )
    if int(recent or 0) >= HINTS_PER_MINUTE:
        return ACCEPTED
    await record_provider_hint(tenant_id, envelope, event)
    return ACCEPTED
