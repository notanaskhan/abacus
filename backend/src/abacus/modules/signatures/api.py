"""Public interface of the signatures module; other modules import only this (ADR-008).

C7 v1 (N-02-T03 stub): the routers, and the slots sources register with. A source (engagement
letters, consents, e-file authorizations, rep letters, notices) registers a resolver that drafts
an envelope's documents and signers from its own record; it gets its gate facts back from
`envelope_gate_facts`. The bodies land with N-02-T08 and T09.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from abacus.kernel.errors import NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext
from abacus.modules.signatures.contract import policies_router, portal_router, router


@dataclass(frozen=True)
class EnvelopeSummary:
    """What a source shows about its envelope: identifiers, the status code and counts."""

    envelope_id: UUID
    status: str
    signed: int
    total: int


@dataclass(frozen=True)
class GateFacts:
    """A gate's facts from envelopes (G3 letter signed; the e-file authorization)."""

    met: bool
    envelope_id: UUID | None
    completed_on: str | None


EnvelopeSource = Callable[[AuthContext, UUID], Awaitable[object]]
_sources: dict[str, EnvelopeSource] = {}


def register_envelope_source(kind: str, resolver: EnvelopeSource) -> None:
    """A source registers once, at import (a second registration is a programming error)."""
    if kind in _sources:
        raise RuntimeError(f"envelope source {kind!r} is already registered")
    _sources[kind] = resolver


async def envelope_summary_for(
    ctx: AuthContext, source_kind: str, source_id: UUID
) -> EnvelopeSummary | None:
    """The newest envelope for a source record (N-02-T09)."""
    raise NotImplementedYet


async def envelope_gate_facts(ctx: AuthContext, gate_kind: str, target_ref: UUID) -> GateFacts:
    """Gate facts for G3 and the e-file authorization (N-02-T09)."""
    raise NotImplementedYet


# The routers the API mounts, in order (P-39; F-03-T07). `/import` and `/summary` are declared
# before `/{envelope_id}` inside `router`.
ROUTERS: tuple[AbacusRouter, ...] = (router, policies_router, portal_router)

__all__ = [
    "ROUTERS",
    "EnvelopeSummary",
    "GateFacts",
    "envelope_gate_facts",
    "envelope_summary_for",
    "register_envelope_source",
]
