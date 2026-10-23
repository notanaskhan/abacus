"""SES delivery events and email suppression (Q-01-T46). PROTECTED.

SES publishes each send's fate through the configuration set to EventBridge, and from there to an
SQS queue. `drain_ses_events` reads a batch, records each event once in `message_deliveries`
(idempotent on the provider event id), suppresses the address after a permanent bounce or a
complaint, emits `message.bounced` or `message.complained`, and deletes the batch. It runs
every minute as `DrainSesEventsWorkflow`.

A send is matched to its firm and message by the two tags `SesTransport` sets (`tenant_id` and
`message_id`), never by address. A recipient address is handled only in memory: it is hashed at
once (HMAC-SHA256 under the suppression pepper) and never stored, logged or emitted.
`send_email` refuses a suppressed address before it reaches the transport, and routes a
synthetic firm's recipient to the mail sink first (F-04-T22, `sink.py`).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Protocol, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import ServiceUnavailable
from abacus.kernel.logging import get_logger
from abacus.kernel.storage import sqs_client
from abacus.kernel.uow import MissingAuditEvent, Ref, Target, uow
from abacus.modules.communications.events import MessageBounced, MessageComplained
from abacus.modules.communications.sink import sink_address
from abacus.modules.communications.transport import transport
from abacus.modules.identity.api import is_synthetic_firm

# Local and test runs only: a fixed pepper, so hashes are stable without configuration.
_LOCAL_PEPPER: Final = b"abacus-local-email-suppression-pepper"
_EVENTS: Final = {
    "Delivery": "delivered",
    "Bounce": "bounced",
    "Complaint": "complained",
    "Reject": "rejected",
    "DeliveryDelay": "delayed",
}
_EVENT_ID: Final = re.compile(r"[A-Za-z0-9._:/-]{1,200}")
_BATCH: Final = 10
# The violation a message records when its address is suppressed: a kind, never the address.
SUPPRESSED: Final = {"kind": "suppressed", "ref": ""}
_log = get_logger(__name__)


def _pepper() -> bytes:
    configured = settings().email_suppression_pepper
    if configured is not None:
        return configured.get_secret_value().encode()
    if settings().environment in ("local", "test"):
        return _LOCAL_PEPPER
    raise ServiceUnavailable("email suppression is not configured")


def address_hash(address: str) -> bytes:
    """The only form an address is kept in: HMAC-SHA256 of the trimmed, case-folded address."""
    return hmac.new(_pepper(), address.strip().casefold().encode(), hashlib.sha256).digest()


_SUPPRESSED = text(
    "SELECT EXISTS (SELECT 1 FROM email_suppressions WHERE address_hash = :hash "
    "AND lifted_at IS NULL)"
)


async def is_suppressed(tenant_id: UUID, address: str) -> bool:
    ctx = TenantContext(tenant_id, "system", "email_suppression")
    async with tenant_session(ctx) as session:
        return bool((await session.execute(_SUPPRESSED, {"hash": address_hash(address)})).scalar())


async def send_email(
    *,
    tenant_id: UUID,
    message_id: UUID,
    to: str,
    subject: str,
    body: str,
    sender_name: str | None = None,
    reply_to: str | None = None,
) -> bool:
    """Send through the transport, unless the firm has suppressed the address: then nothing is
    sent and False is returned, so the caller records the message `blocked` (`suppressed`).

    F-04-T22: a synthetic firm's recipient is routed to the sink first (`sink.py`); a recipient
    the sink can't take is refused the same way (False), logged without the address."""
    if await is_synthetic_firm(TenantContext(tenant_id, "system", "mail_sink")):
        routed = sink_address(to, tenant_id)
        if routed is None:
            _log.warning("email.sink_refused", tenant_id=tenant_id, message_id=message_id)
            return False
        to = routed
    if await is_suppressed(tenant_id, to):
        _log.info("email.suppressed", tenant_id=tenant_id, message_id=message_id)
        return False
    await asyncio.to_thread(
        transport().send,
        to=to,
        subject=subject,
        body=body,
        sender_name=sender_name,
        reply_to=reply_to,
        tenant_id=tenant_id,
        message_id=message_id,
    )
    return True


@dataclass(frozen=True)
class SesEvent:
    provider_event_id: str
    tenant_id: UUID
    message_id: UUID
    event: str
    bounce_kind: str | None
    occurred_at: datetime
    # Clear text, in memory only: hashed by `record_ses_event`, never stored or logged.
    recipients: tuple[str, ...]

    @property
    def suppresses(self) -> bool:
        return self.event == "complained" or self.bounce_kind == "permanent"


def _tag(tags: dict[str, object], name: str) -> UUID | None:
    values = tags.get(name)
    if not isinstance(values, list) or not values:
        return None
    try:
        return UUID(str(cast(list[object], values)[0]))
    except ValueError:
        return None


def _recipients(section: object, key: str) -> tuple[str, ...]:
    if not isinstance(section, dict):
        return ()
    listed = cast(dict[str, object], section).get(key)
    if not isinstance(listed, list):
        return ()
    found: list[str] = []
    for entry in cast(list[object], listed):
        if isinstance(entry, dict):
            address = cast(dict[str, object], entry).get("emailAddress")
            if isinstance(address, str) and 3 <= len(address) <= 320:
                found.append(address)
    return tuple(found)


def parse_ses_event(raw: str) -> SesEvent | None:
    """An SES event from its EventBridge envelope, or None for one that isn't a delivery event of
    ours (another event type, untagged, or malformed). Never raises on hostile input."""
    try:
        envelope = cast(object, json.loads(raw))
    except (ValueError, TypeError):
        return None
    if not isinstance(envelope, dict):
        return None
    outer = cast(dict[str, object], envelope)
    detail, event_id = outer.get("detail"), outer.get("id")
    if not isinstance(detail, dict) or not isinstance(event_id, str):
        return None
    if not _EVENT_ID.fullmatch(event_id):
        return None
    body = cast(dict[str, object], detail)
    event = _EVENTS.get(str(body.get("eventType")))
    mail = body.get("mail")
    if event is None or not isinstance(mail, dict):
        return None
    tags = cast(dict[str, object], mail).get("tags")
    if not isinstance(tags, dict):
        return None
    tenant_id = _tag(cast(dict[str, object], tags), "tenant_id")
    message_id = _tag(cast(dict[str, object], tags), "message_id")
    occurred = outer.get("time")
    if tenant_id is None or message_id is None or not isinstance(occurred, str):
        return None
    try:
        occurred_at = datetime.fromisoformat(occurred.replace("Z", "+00:00"))
    except ValueError:
        return None
    if occurred_at.tzinfo is None:
        return None
    bounce_kind: str | None = None
    recipients: tuple[str, ...] = ()
    if event == "bounced":
        bounce = cast(object, body.get("bounce"))
        section = cast(dict[str, object], bounce) if isinstance(bounce, dict) else {}
        kind = section.get("bounceType")
        bounce_kind = "permanent" if kind == "Permanent" else "transient"
        recipients = _recipients(section, "bouncedRecipients")
    elif event == "complained":
        recipients = _recipients(body.get("complaint"), "complainedRecipients")
    return SesEvent(event_id, tenant_id, message_id, event, bounce_kind, occurred_at, recipients)


_RECORD = text(
    "INSERT INTO message_deliveries (tenant_id, message_id, provider_event_id, event, "
    "bounce_kind, occurred_at) VALUES (:tenant, :message, :event_id, :event, :bounce, :at) "
    "ON CONFLICT (provider_event_id) DO NOTHING RETURNING id"
)
_SUPPRESS = text(
    "INSERT INTO email_suppressions (tenant_id, address_hash, reason) VALUES "
    "(:tenant, :hash, :reason) ON CONFLICT (tenant_id, address_hash) WHERE lifted_at IS NULL "
    "DO NOTHING"
)


async def record_ses_event(event: SesEvent) -> bool:
    """Record one event; True if it was new. A permanent bounce or a complaint suppresses each
    named recipient and emits `message.bounced` or `message.complained`."""
    ctx = TenantContext(event.tenant_id, "system", "ses_events")
    try:
        async with uow(ctx) as tx:
            inserted = (
                await tx.session.execute(
                    _RECORD,
                    {
                        "tenant": event.tenant_id,
                        "message": event.message_id,
                        "event_id": event.provider_event_id,
                        "event": event.event,
                        "bounce": event.bounce_kind,
                        "at": event.occurred_at,
                    },
                )
            ).first()
            if inserted is None:
                return False  # a redelivered event: nothing recorded, nothing audited
            if event.suppresses:
                reason = "complaint" if event.event == "complained" else "bounce"
                for address in event.recipients:
                    await tx.session.execute(
                        _SUPPRESS,
                        {
                            "tenant": event.tenant_id,
                            "hash": address_hash(address),
                            "reason": reason,
                        },
                    )
            if event.event == "bounced":
                tx.emit(MessageBounced(message_id=event.message_id))
            elif event.event == "complained":
                tx.emit(MessageComplained(message_id=event.message_id))
            tx.record(
                f"message.{event.event}",
                target=Target("message", event.message_id),
                after=Ref(suppressed=len(event.recipients) if event.suppresses else 0),
            )
        return True
    except MissingAuditEvent:  # unreachable: every new row is audited above
        return False


@dataclass(frozen=True)
class QueuedEvent:
    receipt: str
    body: str


class SesEventQueue(Protocol):
    def receive(self, limit: int) -> Sequence[QueuedEvent]: ...

    def delete(self, receipts: Sequence[str]) -> None: ...


class SqsSesEventQueue:
    def __init__(self, queue_url: str) -> None:
        self._url = queue_url
        self._client = sqs_client()

    def receive(self, limit: int) -> Sequence[QueuedEvent]:
        answer = self._client.receive_message(
            QueueUrl=self._url, MaxNumberOfMessages=limit, WaitTimeSeconds=0
        )
        return [
            QueuedEvent(m["ReceiptHandle"], m["Body"])
            for m in answer.get("Messages", [])
            if "ReceiptHandle" in m and "Body" in m
        ]

    def delete(self, receipts: Sequence[str]) -> None:
        if receipts:
            self._client.delete_message_batch(
                QueueUrl=self._url,
                Entries=[{"Id": str(n), "ReceiptHandle": r} for n, r in enumerate(receipts)],
            )


_queue: SesEventQueue | None = None


def configure_ses_event_queue(queue: SesEventQueue | None) -> None:
    """Tests and local runs: an in-memory queue (None resets to settings)."""
    global _queue
    _queue = queue


def _ses_queue() -> SesEventQueue | None:
    if _queue is not None:
        return _queue
    url = settings().ses_events_queue_url
    return SqsSesEventQueue(url) if url else None


async def drain_ses_events(batches: int = 5) -> int:
    """Up to `batches` batches from the queue; how many new events were recorded. A message is
    deleted once it is recorded or found to be no event of ours; a failure leaves it queued."""
    queue = _ses_queue()
    if queue is None:
        return 0
    recorded = 0
    for _ in range(batches):
        batch = await asyncio.to_thread(queue.receive, _BATCH)
        if not batch:
            break
        done: list[str] = []
        for message in batch:
            parsed = parse_ses_event(message.body)
            try:
                if parsed is not None and await record_ses_event(parsed):
                    recorded += 1
            except Exception as exc:  # left on the queue; SQS redelivers it
                _log.warning("ses_events.record_failed", error=type(exc).__name__)
                continue
            done.append(message.receipt)
        await asyncio.to_thread(queue.delete, done)
    return recorded


@activity.defn(name="communications.drain_ses_events")
async def drain_ses_events_activity() -> int:
    return await drain_ses_events()
