"""C11's `engagement_letter` kind (N-02-T32; DEC-1458): the renderer `engagements` asks through its
port (`engagements.api.register_letter_renderer`), since `engagements` may not import `reporting`.

The kind's variables provider answers what the composer resolved for the same owner in the current
call (a context variable set around `render`); an unresolved owner gets nothing, so every
declared key refuses with `missing_variable`.

N-02-T33: a partner's approval renders the approved draft final (`finalise_engagement_letter`).
The approval provider confirms only the approval the composer is recording in the same call (a
context variable, like the values), so no other caller can render a letter final; it answers the
approver and the content hash they approved, which C11 checks against the draft (AC-15). A
completed envelope locks the document (`lock_engagement_letter`, C11 AC-19).
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from typing import Final
from uuid import UUID

from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import LetterFinalAsk, LetterRenderAsk, LetterRendered

KIND: Final = "engagement_letter"
OWNER: Final = "engagement_letter"

_resolving: ContextVar[Mapping[UUID, Mapping[str, str]] | None] = ContextVar(
    "abacus_letter_variables", default=None
)


async def _provider(owner: object, scope: object) -> Mapping[str, str]:
    from abacus.modules.reporting.api import OwnerRef

    current = _resolving.get()
    if current is None or not isinstance(owner, OwnerRef) or owner.type != OWNER:
        return {}
    return current.get(owner.id, {})


_approving: ContextVar[LetterFinalAsk | None] = ContextVar("abacus_letter_approval", default=None)
APPROVAL_KIND: Final = "letter_partner_approval"


async def _approval(ref: object) -> tuple[UUID, str] | None:
    from abacus.modules.reporting.api import ApprovalRef

    ask = _approving.get()
    if ask is None or not isinstance(ref, ApprovalRef):
        return None
    if (ref.kind, ref.id, ref.content_hash) != (APPROVAL_KIND, ask.version_id, ask.content_hash):
        return None
    return ask.approver_user_id, ask.content_hash


def ensure_kind() -> None:
    """Register `engagement_letter` with C11 once per process (and again after a test resets)."""
    from abacus.modules.reporting import api as c11

    try:
        c11.document_kind(KIND)
    except c11.UnknownDocumentKind:
        c11.register_document_kind(
            c11.DocumentKind(
                kind=KIND,
                layout="letter",
                variables_provider=_provider,
                approval_provider=_approval,
                retention_record_type="engagement_letter",
                formats=("pdf", "docx"),
            )
        )


async def render_engagement_letter(tx: UnitOfWork, ask: LetterRenderAsk) -> LetterRendered:
    """A C11 draft of the letter, a person's, in the caller's unit of work."""
    from abacus.modules.reporting import api as c11

    ensure_kind()
    token = _resolving.set({ask.owner_id: dict(ask.values)})
    try:
        ticket = await c11.render(
            tx,
            c11.RenderRequest(
                kind=KIND,
                owner_ref=c11.OwnerRef(OWNER, ask.owner_id),
                scope=c11.RenderScope(client_id=ask.client_id, engagement_id=ask.engagement_id),
                template_version_id=ask.template_version_id,
                requested_by=c11.Requester("human", user_id=ask.requested_by),
                formats=("pdf", "docx"),
                clause_states=tuple(
                    c11.ClauseState(k, on) for k, on in sorted(ask.clause_states.items())
                ),
                section_overrides=tuple(
                    c11.SectionOverride(k, paragraphs, ask.requested_by)
                    for k, paragraphs in sorted(ask.overrides.items())
                ),
            ),
        )
    finally:
        _resolving.reset(token)
    return LetterRendered(ticket.generated_document_id, ticket.content_hash)


async def finalise_engagement_letter(tx: UnitOfWork, ask: LetterFinalAsk) -> UUID:
    """The approved draft rendered final, a person's, in the caller's unit of work; answers the
    final version's id."""
    from abacus.modules.reporting import api as c11
    from abacus.modules.reporting import documents as docs

    ensure_kind()
    token = _approving.set(ask)
    try:
        ticket = await c11.render_final(
            tx,
            ask.generated_document_id,
            c11.ApprovalRef(APPROVAL_KIND, ask.version_id, ask.content_hash),
            c11.Requester("human", user_id=ask.approver_user_id),
        )
    finally:
        _approving.reset(token)
    return await docs.version_id(tx, ask.generated_document_id, ticket.version_no)


async def lock_engagement_letter(tx: UnitOfWork, document_id: UUID, cause_ref: str) -> None:
    from abacus.modules.reporting import api as c11

    await c11.lock(tx, document_id, cause_ref)


__all__ = [
    "APPROVAL_KIND",
    "KIND",
    "ensure_kind",
    "finalise_engagement_letter",
    "lock_engagement_letter",
    "render_engagement_letter",
]
