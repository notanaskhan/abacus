"""The respondent's answer to a confirmation (A-08-T19; A-08 §3 F5; SPEC-657 AC-7.x; POR-17; AU-C
505; DEC-5309; red).

A live link principal (A-08-T15) that verified its email submits one answer:

- **One answer, ever.** The response row is unique per confirmation; a second submission answers
  409 `already_answered` naming the original receipt and writes nothing (AC-7.5).
- **The server computes the difference** (ADR-050): per client (the confirmation's book lines)
  minus per respondent (the balance given; agreeing is the book total). The page's figure is
  never stored.
- The answer is the respondent's, sealed at rest; the event `responded` is the link principal's;
  the confirmation moves to `responded` and AUD-14 reads it from the firm's side only. No client
  principal reads it (the firm routes answer a client 404, the portal has no confirmation route).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.assurance.events import ConfirmationResponded
from abacus.modules.identity.api import LinkPrincipal

_AAD_NAME: Final = "assurance.confirmation.respondent"
_AAD_EXPLANATION: Final = "assurance.confirmation.explanation"
_ACTOR: Final = "confirmation.respondent"
CENT: Final = Decimal("0.01")


class AlreadyAnswered(DomainConflict):
    code = "already_answered"


class AttachmentNotYours(DomainInvalid):
    code = "attachment_invalid"


_OPEN: Final = text(
    "SELECT c.status, c.engagement_id, c.work_item_id, "
    "EXISTS (SELECT 1 FROM confirmation_responses r WHERE r.confirmation_id = c.id) AS answered "
    "FROM confirmations c WHERE c.id = :c"
)
_ATTACH: Final = text(
    "INSERT INTO confirmation_attachments (tenant_id, confirmation_id, evidence_version_id, "
    "principal_id) VALUES (:t, :c, :v, :p)"
)
_MINE: Final = text(
    "SELECT evidence_version_id FROM confirmation_attachments WHERE confirmation_id = :c "
    "AND principal_id = :p AND evidence_version_id = ANY(:ids)"
)


async def attach(principal: LinkPrincipal, file_name: str, content: bytes) -> tuple[UUID, int]:
    """A-08-T19 (DEC-5325): one file for the open request, scanned before it is stored (a
    refused file is `file_refused`, nothing kept); 404 once answered or not Sent."""
    if not principal.verified:
        raise NotFound("confirmation")
    from abacus.modules.engagements.api import client_of
    from abacus.modules.evidence.api import file_respondent_copy

    tenant = _tenant(principal)
    async with tenant_session(tenant) as session:
        row = (await session.execute(_OPEN, {"c": principal.subject_id})).mappings().first()
    if row is None or row["status"] != "sent" or row["answered"]:
        raise NotFound("confirmation")
    engagement = cast(UUID, row["engagement_id"])
    client = await client_of(tenant, engagement)
    if client is None:
        raise NotFound("confirmation")
    version = await file_respondent_copy(
        tenant_id=principal.tenant_id,
        client_id=client,
        engagement_id=engagement,
        work_item_id=cast(UUID, row["work_item_id"]),
        file_name=file_name,
        content=content,
        principal_id=principal.principal_id,
    )
    async with uow(tenant) as tx:
        await tx.session.execute(
            _ATTACH,
            {
                "t": principal.tenant_id,
                "c": principal.subject_id,
                "v": version,
                "p": principal.principal_id,
            },
        )
        tx.record(
            "confirmation.attachment_added",
            target=Target("confirmation", principal.subject_id),
            after=Ref(evidence_version_id=version),
        )
    return version, len(content)


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    reference: str
    agrees: bool
    respondent_balance: Decimal
    difference: Decimal
    submitted_at: datetime


_CONFIRMATION: Final = text(
    "SELECT c.id, c.number, c.status, c.engagement_id, (SELECT e.actor_id FROM "
    "confirmation_events e WHERE e.confirmation_id = c.id AND e.kind = 'sent' AND "
    "e.actor_kind = 'human' ORDER BY e.at DESC LIMIT 1) AS sent_by "
    "FROM confirmations c WHERE c.id = :c FOR UPDATE OF c"
)
_BOOKS: Final = text(
    "SELECT coalesce(sum(book_amount), 0) FROM confirmation_lines WHERE confirmation_id = :c"
)
_INSERT: Final = text(
    "INSERT INTO confirmation_responses (tenant_id, confirmation_id, via, agrees, "
    "respondent_name_sealed, confirmed_total, explanation_sealed, attested, "
    "attachment_version_ids, ip_sealed, user_agent, accounts) VALUES (:t, :c, 'respondent_page', "
    ":agrees, :name, :total, :why, true, :files, :ip, :ua, CAST(:accounts AS jsonb)) "
    "ON CONFLICT (confirmation_id) DO NOTHING RETURNING submitted_at"
)
_AAD_IP: Final = "assurance.confirmation.respondent_ip"
_EXISTING: Final = text(
    "SELECT agrees, confirmed_total, submitted_at FROM confirmation_responses "
    "WHERE confirmation_id = :c"
)
_EVENT: Final = text(
    "INSERT INTO confirmation_events (tenant_id, confirmation_id, kind, actor_kind, actor_id) "
    "VALUES (:t, :c, 'responded', 'link_principal', :p)"
)
_STATUS: Final = text(
    "UPDATE confirmations SET status = 'responded', row_version = row_version + 1 "
    "WHERE id = :c AND status = 'sent'"
)


def difference(
    per_client: Decimal, agrees: bool, given: Decimal | None
) -> tuple[Decimal, Decimal]:
    """(the respondent's balance, per client minus per respondent), by code."""
    respondent = per_client if agrees or given is None else Decimal(given)
    return respondent.quantize(CENT), (per_client - respondent).quantize(CENT)


def _tenant(principal: LinkPrincipal) -> TenantContext:
    return TenantContext(principal.tenant_id, "system", _ACTOR)


async def submit(
    principal: LinkPrincipal,
    *,
    agrees: bool,
    balance: Decimal | None,
    respondent_name: str,
    explanation: str | None,
    attachment_ids: list[UUID],
    accounts: list[tuple[str, str | None, Decimal]] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> Receipt:
    """The one answer of a verified link principal; 409 `already_answered` on any replay."""
    if not principal.verified:
        raise NotFound("confirmation")
    tenant = _tenant(principal)
    confirmation_id = principal.subject_id
    if attachment_ids:  # only the files this link uploaded for this confirmation
        async with tenant_session(tenant) as session:
            mine = {
                cast(UUID, r[0])
                for r in await session.execute(
                    _MINE,
                    {"c": confirmation_id, "p": principal.principal_id, "ids": attachment_ids},
                )
            }
        if set(attachment_ids) - mine:
            raise AttachmentNotYours(facts={"field": "attachment_ids"})
    async with uow(tenant) as tx:
        row = (await tx.session.execute(_CONFIRMATION, {"c": confirmation_id})).mappings().first()
        if row is None:
            raise NotFound("confirmation")
        reference = f"C{row['number']}"
        existing = (await tx.session.execute(_EXISTING, {"c": confirmation_id})).first()
        if existing is not None:
            raise AlreadyAnswered(facts={"receipt_id": f"{reference}-R1"})
        if row["status"] != "sent":
            raise NotFound("confirmation")
        books = Decimal(await tx.session.scalar(_BOOKS, {"c": confirmation_id}) or 0)
        respondent, diff = difference(books, agrees, balance)
        submitted = await tx.session.scalar(
            _INSERT,
            {
                "t": principal.tenant_id,
                "c": confirmation_id,
                "agrees": agrees,
                "name": await seal(principal.tenant_id, respondent_name.encode(), _AAD_NAME),
                "total": respondent,
                "why": (
                    await seal(principal.tenant_id, explanation.encode(), _AAD_EXPLANATION)
                    if explanation
                    else None
                ),
                "files": list(attachment_ids),
                "ip": None if not ip else await seal(principal.tenant_id, ip.encode(), _AAD_IP),
                "ua": (user_agent or "")[:400] or None,
                "accounts": json.dumps(
                    [
                        {"description": d, "account_last4": last4, "balance": str(b)}
                        for d, last4, b in (accounts or [])
                    ]
                ),
            },
        )
        if submitted is None:  # a concurrent answer won the unique row
            raise AlreadyAnswered(facts={"receipt_id": f"{reference}-R1"})
        await tx.session.execute(
            _EVENT,
            {"t": principal.tenant_id, "c": confirmation_id, "p": str(principal.principal_id)},
        )
        await tx.session.execute(_STATUS, {"c": confirmation_id})
        tx.record("confirmation.responded", target=Target("confirmation", confirmation_id))
        if row["sent_by"] is not None:  # A-08 §4.7: the sender hears it was answered
            tx.emit(
                ConfirmationResponded(
                    confirmation_id=confirmation_id,
                    engagement_id=cast(UUID, row["engagement_id"]),
                    user_id=UUID(str(row["sent_by"])),
                )
            )
    return Receipt(
        receipt_id=f"{reference}-R1",
        reference=reference,
        agrees=agrees,
        respondent_balance=respondent,
        difference=diff,
        submitted_at=cast(datetime, submitted),
    )


async def original_receipt(principal: LinkPrincipal) -> Receipt | None:
    """The receipt of the answer already given (the answered page and the 409's body)."""
    tenant = _tenant(principal)
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text("SELECT number FROM confirmations WHERE id = :c"), {"c": principal.subject_id}
            )
        ).first()
        found = (await session.execute(_EXISTING, {"c": principal.subject_id})).first()
        books = Decimal(await session.scalar(_BOOKS, {"c": principal.subject_id}) or 0)
    if row is None or found is None:
        return None
    total = Decimal(found[1])
    return Receipt(
        receipt_id=f"C{row[0]}-R1",
        reference=f"C{row[0]}",
        agrees=bool(found[0]),
        respondent_balance=total,
        difference=(books - total).quantize(CENT),
        submitted_at=found[2],
    )
