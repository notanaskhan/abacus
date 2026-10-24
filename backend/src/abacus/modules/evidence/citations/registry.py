"""The citable kinds and their verifiers (P-03-T06; ADR-166 §2; DEC-218). PROTECTED.

`register_citable(kind, verifier, display)` gives one of the ten kinds a code verifier and a
display function. Evidence registers `document_text`, `sheet_cell` and `request_item`; a source's
owner registers its own kind from its `api.py` when it lands (K-01 `methodology_step`, A-04
`workpaper_cell`, T-04 `tax_form_line`, ...). A kind with no verifier is still recorded, unverified
with `locator_invalid`, until its owner registers one. A kind is registered once; an eleventh kind
needs a new ADR.

A verifier first authorises the acting principal to read the cited source on the anchor's
engagement (an anchor with no engagement can't cite engagement evidence), so verification is never
an oracle across engagements; then it reads the source inside the writer's unit of work and
returns a `Verdict`: the
outcome, the normalised locator (with any resolved box), the server-derived `match_id`, the hash
of the words the quote resolved to, and the source's printed value. It never stores, logs or
returns the quote itself. A display function renders `title` and `loc` from the locator by code,
never from model text (INV-2), reading with the reader's session (P-03-T08: a read opens no unit of
work).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from typing import Final, Literal, get_args
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.uow import UnitOfWork
from abacus.modules.evidence.citations.matching import Reason
from abacus.modules.identity.api import Actor

CitationKind = Literal[
    "document_text",
    "sheet_cell",
    "ledger_line",
    "workpaper_cell",
    "methodology_step",
    "policy_rule",
    "record_field",
    "tax_form_line",
    "artifact_cell",
    "request_item",
]
KINDS: Final = frozenset(get_args(CitationKind))
NIL: Final = UUID(int=0)

# Each kind's source and the locator field naming it (C4 §3.1). `record_field` names its source
# type in the locator itself.
SOURCES: Final[dict[str, tuple[str, str]]] = {
    "document_text": ("evidence_version", "evidence_version_id"),
    "sheet_cell": ("evidence_version", "evidence_version_id"),
    "ledger_line": ("ledger_snapshot", "ledger_snapshot_id"),
    "workpaper_cell": ("workpaper_sheet", "sheet_id"),
    "methodology_step": ("methodology_template_version", "template_version_id"),
    "policy_rule": ("threshold_policy", "threshold_policy_id"),
    "record_field": ("record", "record_id"),
    "tax_form_line": ("tax_return", "return_id"),
    "artifact_cell": ("run_artifact", "run_artifact_id"),
    "request_item": ("request_item", "request_item_id"),
}


@dataclass(frozen=True)
class CitationClaim:
    """What a writer says it cites. `quote` and `value` are checked against the source and
    never stored: the row keeps only the hash of the words the quote resolved to and the value as
    the source prints it."""

    kind: str
    locator: Mapping[str, object]
    quote: str | None = None
    value: str | None = None


@dataclass(frozen=True)
class Anchor:
    """Where the citation is used: the citing record, its cell or line, and its scope. An
    engagement source must be in `engagement_id`, which the actor must be allowed to read."""

    type: str
    id: UUID
    ref: str | None = None
    locator: Mapping[str, object] | None = None
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None
    client_id: UUID | None = None


@dataclass(frozen=True)
class Verdict:
    reason: Reason | None
    source_type: str
    source_id: UUID
    locator: dict[str, object] = field(default_factory=dict[str, object])
    source_version: str | None = None
    match_id: str | None = None
    quote_sha256: bytes | None = None
    value_text: str | None = None

    @property
    def verified(self) -> bool:
        return self.reason is None


@dataclass(frozen=True)
class Display:
    title: str
    loc: str


# (the writer's unit of work, the acting principal, the claim, where it is used)
Verifier = Callable[[UnitOfWork, Actor, CitationClaim, Anchor], Awaitable[Verdict]]
# (the reader's tenant session, the stored locator)
Displayer = Callable[[AsyncSession, Mapping[str, object]], Awaitable[Display]]


@dataclass(frozen=True)
class Citable:
    verifier: Verifier
    display: Displayer
    version: str


_registry: dict[str, Citable] = {}


def register_citable(
    kind: CitationKind, verifier: Verifier, display: Displayer, *, version: str = "v1"
) -> None:
    """Give `kind` its verifier and display function (once; at the owner's import)."""
    if kind not in KINDS:
        raise ValueError(f"{kind!r} is not a citation kind (ADR-166: ten kinds)")
    known = _registry.get(kind)
    if known is not None and (known.verifier, known.display) != (verifier, display):
        raise ValueError(f"{kind} already has a verifier")
    _registry[kind] = Citable(verifier, display, version)


def citable(kind: str) -> Citable | None:
    return _registry.get(kind)


def source_of(claim: CitationClaim) -> tuple[str, UUID]:
    """The claim's source type and id as its locator names them (the nil id when it doesn't),
    for a row whose verifier can't read it."""
    source_type, field_name = SOURCES.get(claim.kind, ("unknown", "id"))
    if claim.kind == "record_field":
        named = claim.locator.get("record_type")
        if isinstance(named, str) and named.isidentifier() and named.islower():
            source_type = named[:40]
    raw = claim.locator.get(field_name)
    try:
        return source_type, UUID(str(raw)) if raw is not None else NIL
    except ValueError:
        return source_type, NIL


def unverifiable(claim: CitationClaim) -> Verdict:
    """A claim no registered verifier reads: kept, unverified, `locator_invalid`."""
    source_type, source_id = source_of(claim)
    return Verdict("locator_invalid", source_type, source_id)


__all__ = [
    "KINDS",
    "NIL",
    "SOURCES",
    "Anchor",
    "Citable",
    "CitationClaim",
    "CitationKind",
    "Display",
    "Displayer",
    "Verdict",
    "Verifier",
    "citable",
    "register_citable",
    "source_of",
    "unverifiable",
]
