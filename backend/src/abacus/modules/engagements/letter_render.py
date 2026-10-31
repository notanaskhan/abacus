"""The engagement letter's renderer port (N-02-T32 review; ADR-008; DEC-1458).

`reporting` (C11) may depend on `engagements`, never the other way round, so the letter composer
does not import the renderer. It hands a `LetterRenderAsk` to the renderer `reporting` registered
here at import (`register_letter_renderer`), inside the caller's unit of work, and gets back the
C11 draft's document and content hash. Values are resolved by this module from the database and
passed whole; the renderer keeps only the template version's declared keys.

N-02-T33 adds two slots the same way: the finaliser (a partner's approval renders the approved
draft final, with the approval C11 checks against the content hash) and the locker (a completed
envelope locks the letter's document, C11 AC-19).
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


@dataclass(frozen=True)
class LetterFinalAsk:
    """A partner approved `version_id`'s content hash: render that draft final (N-02-T33)."""

    generated_document_id: UUID
    version_id: UUID
    content_hash: str
    approver_user_id: UUID


LetterRenderer = Callable[[UnitOfWork, LetterRenderAsk], Awaitable[LetterRendered]]
LetterFinaliser = Callable[[UnitOfWork, LetterFinalAsk], Awaitable[UUID]]
LetterLocker = Callable[[UnitOfWork, UUID, str], Awaitable[None]]
_RENDERERS: list[LetterRenderer] = []
_FINALISERS: list[LetterFinaliser] = []
_LOCKERS: list[LetterLocker] = []


def register_letter_renderer(renderer: LetterRenderer) -> None:
    """`reporting` registers C11's letter render at import; a second registration replaces it."""
    _RENDERERS[:] = [renderer]


async def render_letter(tx: UnitOfWork, ask: LetterRenderAsk) -> LetterRendered:
    if not _RENDERERS:
        raise RuntimeError("no letter renderer is registered (reporting.api not imported)")
    return await _RENDERERS[0](tx, ask)


def register_letter_finaliser(finaliser: LetterFinaliser) -> None:
    _FINALISERS[:] = [finaliser]


async def finalise_letter(tx: UnitOfWork, ask: LetterFinalAsk) -> UUID:
    """The final version's id (`generated_document_versions.id`), the document Send names."""
    if not _FINALISERS:
        raise RuntimeError("no letter finaliser is registered (reporting.api not imported)")
    return await _FINALISERS[0](tx, ask)


def register_letter_locker(locker: LetterLocker) -> None:
    _LOCKERS[:] = [locker]


async def lock_letter(tx: UnitOfWork, generated_document_id: UUID, cause_ref: str) -> None:
    if not _LOCKERS:
        raise RuntimeError("no letter locker is registered (reporting.api not imported)")
    await _LOCKERS[0](tx, generated_document_id, cause_ref)


__all__ = [
    "LetterFinalAsk",
    "LetterFinaliser",
    "LetterLocker",
    "LetterRenderAsk",
    "LetterRendered",
    "LetterRenderer",
    "finalise_letter",
    "lock_letter",
    "register_letter_finaliser",
    "register_letter_locker",
    "register_letter_renderer",
    "render_letter",
]
