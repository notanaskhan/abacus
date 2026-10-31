"""The engagement letter's renderer port (N-02-T32 review; ADR-008; DEC-1458).

`reporting` (C11) may depend on `engagements`, never the other way round, so the letter composer
does not import the renderer. It hands a `LetterRenderAsk` to the renderer `reporting` registered
here at import (`register_letter_renderer`), inside the caller's unit of work, and gets back the
C11 draft's document and content hash. Values are resolved by this module from the database and
passed whole; the renderer keeps only the template version's declared keys.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from uuid import UUID

from abacus.kernel.uow import UnitOfWork


@dataclass(frozen=True)
class LetterRenderAsk:
    owner_id: UUID
    client_id: UUID
    engagement_id: UUID
    template_version_id: UUID
    requested_by: UUID  # a person: the composer refuses any other caller
    values: Mapping[str, str]
    clause_states: Mapping[str, bool] = field(default_factory=dict[str, bool])
    overrides: Mapping[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])


@dataclass(frozen=True)
class LetterRendered:
    generated_document_id: UUID
    content_hash: str


LetterRenderer = Callable[[UnitOfWork, LetterRenderAsk], Awaitable[LetterRendered]]
_RENDERERS: list[LetterRenderer] = []


def register_letter_renderer(renderer: LetterRenderer) -> None:
    """`reporting` registers C11's letter render at import; a second registration replaces it."""
    _RENDERERS[:] = [renderer]


async def render_letter(tx: UnitOfWork, ask: LetterRenderAsk) -> LetterRendered:
    if not _RENDERERS:
        raise RuntimeError("no letter renderer is registered (reporting.api not imported)")
    return await _RENDERERS[0](tx, ask)


__all__ = [
    "LetterRenderAsk",
    "LetterRendered",
    "LetterRenderer",
    "register_letter_renderer",
    "render_letter",
]
