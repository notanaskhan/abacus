"""Envelope sources and the G3 letter gate (N-02-T09; N-02 §3.12, §8.2; C7; DEC-820).

**Sources.** A source (engagement letters, consents, e-file authorizations, rep letters, notices)
registers once, at import, what an envelope drafted from one of its records needs: providers for
the documents and the signers, the gate it meets, the retention record type, its own pre-send
checks and the label a completed envelope shows. The slot fails closed: an unregistered kind
cannot draft (`unknown_envelope_source`), and a second registration is a programming error.
`engagement_letter` is the first source; its document and signer providers draft from the letter
composer (N-02-T32), so until then they refuse with 501 and record mode is the way in.

**G3.** The engagement-letter gate is met only by (a) a completed, non-superseded letter envelope
carrying a client signature and a firm countersignature, (b) a completed, non-superseded
record-mode letter import, or (c) a letter recorded through `letter.record` (engagements' own
record, kept as the third source). P-07's interim provider is replaced through
`engagements.api.replace_gate_provider`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotImplementedYet
from abacus.modules.engagements.api import GateFact, recorded_letter, replace_gate_provider
from abacus.modules.identity.api import AuthContext

LETTER: Final = "engagement_letter"
LETTER_GATE: Final = "G3"

DocumentsProvider = Callable[[AuthContext, UUID], Awaitable[Sequence[object]]]
SignersProvider = Callable[[AuthContext, UUID], Awaitable[Sequence[object]]]
Check = Callable[[AuthContext, UUID], Awaitable[Sequence[str]]]


class UnknownEnvelopeSource(DomainConflict):
    """No source of this kind is registered: nothing can be drafted from it."""

    code = "unknown_envelope_source"


@dataclass(frozen=True)
class EnvelopeSource:
    kind: str
    documents: DocumentsProvider
    signers: SignersProvider
    retention_record_type: str
    gate: str | None = None
    checks: tuple[Check, ...] = ()
    completed_label: str = "Completed"


_SOURCES: dict[str, EnvelopeSource] = {}


def register_envelope_source(source: EnvelopeSource) -> None:
    """A source registers once, at import; the same source again (a reload) replaces itself."""
    known = _SOURCES.get(source.kind)
    if known is not None and known != source:
        raise RuntimeError(f"envelope source {source.kind!r} is already registered")
    _SOURCES[source.kind] = source


def envelope_source(kind: str) -> EnvelopeSource:
    """The registered source, or `unknown_envelope_source` (fail closed)."""
    found = _SOURCES.get(kind)
    if found is None:
        raise UnknownEnvelopeSource(facts={"kind": kind})
    return found


def registered_sources() -> frozenset[str]:
    return frozenset(_SOURCES)


async def _letter_documents(ctx: AuthContext, engagement_id: UUID) -> Sequence[object]:
    raise NotImplementedYet  # the letter composer drafts letters (N-02-T32)


async def _letter_signers(ctx: AuthContext, engagement_id: UUID) -> Sequence[object]:
    raise NotImplementedYet  # the letter composer names the signers (N-02-T32)


_LETTER_ENVELOPE = text(
    "SELECT e.id FROM envelopes e WHERE e.engagement_id = :engagement "
    "AND e.purpose = 'engagement_letter' AND e.status = 'completed' AND e.superseded_at IS NULL "
    "AND (e.provider = 'record' OR ("
    "  EXISTS (SELECT 1 FROM envelope_signers s WHERE s.envelope_id = e.id "
    "          AND s.party_kind = 'contact' AND s.role = 'signer' AND s.status = 'signed') "
    "  AND EXISTS (SELECT 1 FROM envelope_signers s WHERE s.envelope_id = e.id "
    "          AND s.party_kind = 'user' AND s.role = 'countersigner' AND s.status = 'signed'))) "
    "ORDER BY e.completed_at DESC LIMIT 1"
)


async def letter_envelope(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """The engagement's newest envelope that meets G3 by itself (sources a and b)."""
    async with tenant_session(tenant) as session:
        return await session.scalar(_LETTER_ENVELOPE, {"engagement": engagement_id})


async def letter_gate(tenant: TenantContext, engagement_id: UUID) -> GateFact:
    """G3: a qualifying letter envelope, or engagements' recorded letter."""
    if await letter_envelope(tenant, engagement_id) is not None:
        return GateFact(met=True)
    return await recorded_letter(tenant, engagement_id)


def register_letter_source() -> None:
    register_envelope_source(
        EnvelopeSource(
            kind=LETTER,
            documents=_letter_documents,
            signers=_letter_signers,
            retention_record_type="signature_evidence",
            gate=LETTER_GATE,
            completed_label="Signed",
        )
    )
    replace_gate_provider(LETTER_GATE, letter_gate)
