"""Intake ingest (N-01-T09; N-01 §3, §4.3; ADR-210 clauses 1-5; DEC-821).

One model, three channels: `email` (the scenario loader now, `register_inbound_transport` later),
`portal_upload` (N-01-T14) and `staff_logged` (Log received documents, DV-1). Every inbound message
goes through `record_inbound_message`; every file through `add_attachment`.

- **Threading:** an email whose `In-Reply-To` or `References` names a message the firm holds joins
  that message's thread; anything else, and every staff-logged or portal batch, starts one.
- **Matching** (deterministic, never a model): the client a person named (`staff_selected`), the
  named contact's client, the portal principal's scope, or a live sender rule on the address's
  HMAC; otherwise unmatched (`none`, the intake scope's only, DEC-75).
- **Files:** at most 50 MB, typed from the bytes, scanned before anything is stored and refused
  closed when the scanner is down (the evidence upload path's `checked`); stored encrypted and
  write-once by fingerprint. An attachment of a matched thread is `waiting`, of an unmatched one
  `new`. The same fingerprint already held is flagged `duplicate_hash`, never refused.
- **Bodies and notes** are sealed (Restricted); the sender's address is kept as an HMAC only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal
from uuid import UUID, uuid4

from sqlalchemy import text

from abacus.kernel.clock import system_now
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.communications.deliveries import address_hash
from abacus.modules.communications.events import InboundMessageRecorded, InboxAttachmentReceived
from abacus.modules.evidence.api import screen_and_stage
from abacus.modules.organisations.api import client_exists, contact_client

Channel = Literal["email", "portal_upload", "staff_logged"]
CHECKER_VERSION: Final = "intake-1"
_SOURCE: Final = {"email": "mailbox", "portal_upload": "portal", "staff_logged": "staff"}
_BODY_KIND: Final = {"email": "email_text", "portal_upload": "portal_note"}


@dataclass(frozen=True)
class Inbound:
    """One message as its channel delivered it; strings are hostile (ADR-052)."""

    channel: Channel
    sender_display: str
    subject: str
    received_at: datetime
    body: str | None = None
    sender_address: str | None = None
    internet_message_id: str | None = None
    in_reply_to: str | None = None
    references: tuple[str, ...] = ()
    client_id: UUID | None = None
    client_entity_id: UUID | None = None
    from_contact_id: UUID | None = None
    principal_id: UUID | None = None
    logged_by: UUID | None = None
    received_via: str | None = None
    source_display: str | None = None


@dataclass(frozen=True)
class Recorded:
    thread_id: UUID
    message_id: UUID
    client_id: UUID | None


@dataclass(frozen=True)
class Received:
    attachment_id: UUID
    file_name: str
    status: str
    duplicate_of: UUID | None


def _clip(value: str, limit: int) -> str:
    return "".join(c for c in value if c.isprintable())[:limit].strip() or "(none)"


_BY_MESSAGE_ID = text(
    "SELECT thread_id FROM inbound_messages WHERE internet_message_id = ANY(:ids) "
    "ORDER BY received_at DESC LIMIT 1"
)
_THREAD_CLIENT = text("SELECT client_id FROM inbox_threads WHERE id = :id")
_SENDER_RULE = text(
    "SELECT client_id FROM inbox_sender_rules WHERE address_hmac = :hmac AND revoked_at IS NULL"
)


async def _match(
    tenant: TenantContext, given: Inbound, hmac_hex: str | None
) -> tuple[UUID | None, str]:
    if given.client_id is not None:
        if not await client_exists(tenant, given.client_id):
            raise NotFound("client")
        return given.client_id, "staff_selected"
    async with tenant_session(tenant) as session:
        if given.from_contact_id is not None:
            owner = await contact_client(session, given.from_contact_id)
            if owner is None:
                raise NotFound("contact")
            return owner, "contact_email"
        if hmac_hex is not None:
            ruled = await session.scalar(_SENDER_RULE, {"hmac": hmac_hex})
            if ruled is not None:
                return ruled, "sender_rule"
    return None, "none"


async def record_inbound_message(tenant: TenantContext, given: Inbound) -> Recorded:
    """Thread, match and store one inbound message (no files). The caller authorised it: a
    person's `inbox.log_intake`, a portal principal's scope, or the transport's system actor."""
    hmac_hex = address_hash(given.sender_address).hex() if given.sender_address else None
    thread_id: UUID | None = None
    client_id: UUID | None = None
    method = "none"
    linked = [i for i in (given.in_reply_to, *given.references) if i]
    if given.channel == "email" and linked:
        async with tenant_session(tenant) as session:
            thread_id = await session.scalar(_BY_MESSAGE_ID, {"ids": linked[:100]})
            client_id = (
                await session.scalar(_THREAD_CLIENT, {"id": thread_id}) if thread_id else None
            )
        method = "none" if client_id is None else "contact_email"
    if thread_id is None:
        client_id, method = await _match(tenant, given, hmac_hex)
    message_id = uuid4()
    sender = _clip(given.sender_display, 320)
    subject = _clip(given.subject, 500)
    sealed = (
        await seal(tenant.tenant_id, given.body.encode(), f"inbound_message:{message_id}")
        if given.body
        else None
    )
    async with uow(tenant) as tx:
        if thread_id is None:
            thread_id = uuid4()
            manual = method == "staff_selected"
            await tx.session.execute(
                text(
                    "INSERT INTO inbox_threads (id, tenant_id, source_kind, source_display, "
                    "client_id, client_entity_id, subject_display, sender_display, match_method, "
                    "matched_by, matched_at, first_received_at, last_received_at) VALUES (:id, "
                    ":tenant, :source, :source_display, :client, :entity, :subject, :sender, "
                    ":method, :matched_by, :matched_at, :at, :at)"
                ),
                {
                    "id": thread_id,
                    "tenant": tenant.tenant_id,
                    "source": _SOURCE[given.channel],
                    "source_display": given.source_display,
                    "client": client_id,
                    "entity": given.client_entity_id if client_id is not None else None,
                    "subject": subject,
                    "sender": sender,
                    "method": method,
                    "matched_by": given.logged_by if manual else None,
                    "matched_at": system_now() if manual else None,
                    "at": given.received_at,
                },
            )
            tx.record(
                "inbox_thread.created",
                target=Target("inbox_thread", thread_id),
                after=Ref(messages=1),
            )
        else:
            await tx.session.execute(
                text(
                    "UPDATE inbox_threads SET last_received_at = greatest(last_received_at, :at) "
                    "WHERE id = :id"
                ),
                {"id": thread_id, "at": given.received_at},
            )
        await tx.session.execute(
            text(
                "INSERT INTO inbound_messages (id, tenant_id, thread_id, channel, received_via, "
                "sender_display, sender_address_hmac, sender_contact_id, sender_principal_id, "
                "logged_by_user_id, internet_message_id, in_reply_to, reference_ids, "
                "subject_display, body_sealed, body_kind, received_at) VALUES (:id, :tenant, "
                ":thread, :channel, :via, :sender, :hmac, :contact, :principal, :logged_by, "
                ":internet_id, :reply_to, :refs, :subject, :body, :body_kind, :at)"
            ),
            {
                "id": message_id,
                "tenant": tenant.tenant_id,
                "thread": thread_id,
                "channel": given.channel,
                "via": given.received_via,
                "sender": sender,
                "hmac": hmac_hex,
                "contact": given.from_contact_id,
                "principal": given.principal_id,
                "logged_by": given.logged_by,
                "internet_id": given.internet_message_id,
                "reply_to": given.in_reply_to,
                "refs": list(given.references[:100]) or None,
                "subject": subject,
                "body": sealed,
                "body_kind": (
                    None if sealed is None else _BODY_KIND.get(given.channel, "staff_note")
                ),
                "at": given.received_at,
            },
        )
        tx.record(
            "inbound_message.recorded",
            target=Target("inbound_message", message_id),
            after=Ref(thread_id=thread_id),
        )
        tx.emit(
            InboundMessageRecorded(
                thread_id=thread_id,
                message_id=message_id,
                channel=given.channel,
                client_id=client_id,
            )
        )
    return Recorded(thread_id, message_id, client_id)


_MESSAGE = text(
    "SELECT m.thread_id, m.channel, m.logged_by_user_id, t.client_id FROM inbound_messages m "
    "JOIN inbox_threads t ON t.id = m.thread_id WHERE m.id = :id"
)
_SAME_FINGERPRINT = text(
    "SELECT id FROM inbox_attachments WHERE fingerprint = :fp ORDER BY created_at LIMIT 1"
)


@dataclass(frozen=True)
class MessageFacts:
    thread_id: UUID
    channel: str
    logged_by: UUID | None
    client_id: UUID | None


async def message_facts(tenant: TenantContext, message_id: UUID) -> MessageFacts:
    async with tenant_session(tenant) as session:
        row = (await session.execute(_MESSAGE, {"id": message_id})).one_or_none()
    if row is None:
        raise NotFound("inbound_message")
    return MessageFacts(row.thread_id, row.channel, row.logged_by_user_id, row.client_id)


async def add_attachment(
    tenant: TenantContext, message_id: UUID, *, file_name: str, content: bytes
) -> Received:
    """One file of a message: scanned and stored, or refused with nothing stored."""
    facts = await message_facts(tenant, message_id)
    screened = await screen_and_stage(tenant.tenant_id, content, file_name, None)
    async with tenant_session(tenant) as session:
        duplicate = await session.scalar(_SAME_FINGERPRINT, {"fp": screened.sha256})
    attachment_id = uuid4()
    status = "new" if facts.client_id is None else "waiting"
    async with uow(tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO inbox_attachments (id, tenant_id, message_id, thread_id, client_id, "
                "file_name, media_type, size_bytes, fingerprint, storage_key, "
                "storage_version_id, key_mode, status) VALUES (:id, :tenant, :message, :thread, "
                ":client, :name, :media, :size, :fp, :key, :version, 'content', :status)"
            ),
            {
                "id": attachment_id,
                "tenant": tenant.tenant_id,
                "message": message_id,
                "thread": facts.thread_id,
                "client": facts.client_id,
                "name": screened.file_name,
                "media": screened.media_type,
                "size": screened.stored.size,
                "fp": screened.sha256,
                "key": screened.stored.key,
                "version": screened.stored.version_id,
                "status": status,
            },
        )
        if duplicate is not None:
            await tx.session.execute(
                text(
                    "INSERT INTO inbox_attachment_flags (tenant_id, attachment_id, run_no, kind, "
                    "severity, facts, checker_version) VALUES (:tenant, :attachment, 1, "
                    "'duplicate_hash', 'info', jsonb_build_object('duplicate_of', :dup), "
                    ":checker)"
                ),
                {
                    "tenant": tenant.tenant_id,
                    "attachment": attachment_id,
                    "dup": str(duplicate),
                    "checker": CHECKER_VERSION,
                },
            )
        tx.record(
            "inbox_attachment.received",
            target=Target("inbox_attachment", attachment_id),
            after=Ref(message_id=message_id, fingerprint=screened.sha256),
        )
        tx.emit(
            InboxAttachmentReceived(
                attachment_id=attachment_id,
                message_id=message_id,
                thread_id=facts.thread_id,
                status=status,
            )
        )
    return Received(attachment_id, screened.file_name, status, duplicate)
