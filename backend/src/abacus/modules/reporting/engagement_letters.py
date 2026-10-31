"""C11's `engagement_letter` kind (N-02-T32; DEC-1458): the renderer `engagements` asks through its
port (`engagements.api.register_letter_renderer`), since `engagements` may not import `reporting`.

The kind's variables provider answers what the composer resolved for the same owner in the current
call (a context variable set around `render`); an unresolved owner gets nothing, so every
declared key refuses with `missing_variable`. Approvals are N-02-T33's: until then the approval
provider answers None and no letter renders final.
"""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from typing import Final
from uuid import UUID

from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import LetterRenderAsk, LetterRendered

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


async def _approval(ref: object) -> tuple[UUID, str] | None:
    return None


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


__all__ = ["KIND", "ensure_kind", "render_engagement_letter"]
