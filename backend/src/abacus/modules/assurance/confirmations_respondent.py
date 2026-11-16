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

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.identity.api import LinkPrincipal

_AAD_NAME: Final = "assurance.confirmation.respondent"
_AAD_EXPLANATION: Final = "assurance.confirmation.explanation"
_ACTOR: Final = "confirmation.respondent"
CENT: Final = Decimal("0.01")


class AlreadyAnswered(DomainConflict):
    code = "already_answered"


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    reference: str
    agrees: bool
    respondent_balance: Decimal
    difference: Decimal
    submitted_at: datetime


_CONFIRMATION: Final = text(
    "SELECT id, number, status FROM confirmations WHERE id = :c FOR UPDATE"
)
_BOOKS: Final = text(
    "SELECT coalesce(sum(book_amount), 0) FROM confirmation_lines WHERE confirmation_id = :c"
)
_INSERT: Final = text(
    "INSERT INTO confirmation_responses (tenant_id, confirmation_id, via, agrees, "
    "respondent_name_sealed, confirmed_total, explanation_sealed, attested, "
    "attachment_version_ids) VALUES (:t, :c, 'respondent_page', :agrees, :name, :total, :why, "
    "true, :files) ON CONFLICT (confirmation_id) DO NOTHING RETURNING submitted_at"
)
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
) -> Receipt:
    """The one answer of a verified link principal; 409 `already_answered` on any replay."""
    if not principal.verified:
        raise NotFound("confirmation")
    tenant = _tenant(principal)
    confirmation_id = principal.subject_id
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
