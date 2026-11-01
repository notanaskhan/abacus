"""The engagement letter's sender port (N-02-T33; ADR-008; DEC-1468).

`signatures` (C7) depends on `engagements`, never the reverse, so Send does not import the
envelope builder. `signatures` registers here at import a sender that drafts an envelope from its
`engagement_letter` source for the engagement (`builder.create_draft`, its own unit of work) and
answers the envelope's id; the source reads what it prefills back through
`engagements.api.letter_for_envelope`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext

LetterSender = Callable[[AuthContext, UUID], Awaitable[UUID]]
_SENDERS: list[LetterSender] = []


def register_letter_sender(sender: LetterSender) -> None:
    """`signatures` registers once at import; a second registration replaces it."""
    _SENDERS[:] = [sender]


async def send_letter_envelope(ctx: AuthContext, engagement_id: UUID) -> UUID:
    if not _SENDERS:
        raise RuntimeError("no letter sender is registered (signatures.api not imported)")
    return await _SENDERS[0](ctx, engagement_id)


# N-02-T35: the letter envelope's C7 status (`declined`, `expired`, `voided`, ...), so a person
# can withdraw an envelope that ended unsigned. Unregistered, no envelope has ended (fail closed).
LetterEnvelopeStatus = Callable[[TenantContext, UUID], Awaitable[str | None]]
_STATUS: list[LetterEnvelopeStatus] = []


def register_letter_envelope_status(status: LetterEnvelopeStatus) -> None:
    _STATUS[:] = [status]


async def letter_envelope_status(tenant: TenantContext, envelope_id: UUID) -> str | None:
    return await _STATUS[0](tenant, envelope_id) if _STATUS else None


# N-02-T37 (ENG-04 d, e): when the envelope went out and when each side signed, so the composer
# reads "Sent Sep 8 · 0 of 2 signed" and "Signed by … · countersigned by …" live. Unregistered,
# nothing is known (the fields stay empty).
@dataclass(frozen=True)
class LetterSigning:
    sent_at: datetime | None
    signed_at: Mapping[Literal["client", "firm"], datetime]


LetterEnvelopeSigning = Callable[[TenantContext, UUID], Awaitable[LetterSigning | None]]
_SIGNING: list[LetterEnvelopeSigning] = []


def register_letter_envelope_signing(signing: LetterEnvelopeSigning) -> None:
    _SIGNING[:] = [signing]


async def letter_envelope_signing(
    tenant: TenantContext, envelope_id: UUID
) -> LetterSigning | None:
    return await _SIGNING[0](tenant, envelope_id) if _SIGNING else None


__all__ = [
    "LetterEnvelopeSigning",
    "LetterEnvelopeStatus",
    "LetterSender",
    "LetterSigning",
    "letter_envelope_signing",
    "letter_envelope_status",
    "register_letter_envelope_signing",
    "register_letter_envelope_status",
    "register_letter_sender",
    "send_letter_envelope",
]
