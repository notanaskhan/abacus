"""The engagement letter's sender port (N-02-T33; ADR-008; DEC-1468).

`signatures` (C7) depends on `engagements`, never the reverse, so Send does not import the
envelope builder. `signatures` registers here at import a sender that drafts an envelope from its
`engagement_letter` source for the engagement (`builder.create_draft`, its own unit of work) and
answers the envelope's id; the source reads what it prefills back through
`engagements.api.letter_for_envelope`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

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


__all__ = ["LetterSender", "register_letter_sender", "send_letter_envelope"]
