"""Envelope sources and the G3 letter gate (N-02-T09; N-02 §3.12, §8.2; C7; DEC-820).

**Sources.** A source (engagement letters, consents, e-file authorizations, rep letters, notices)
registers once, at import, what an envelope drafted from one of its records needs: providers for
the documents and the signers, the gate it meets, the retention record type, its own pre-send
checks and the label a completed envelope shows. The slot fails closed: an unregistered kind
cannot draft (`unknown_envelope_source`), and a second registration is a programming error.
`engagement_letter` is the first source. Its record is an approved letter version (N-02-T33):
the draft names the C11 final the approval rendered (by its content hash until the bytes land,
P-11-T11), the client's signing officer (email code) and then the approving partner's
countersignature (firm SSO, routing group 2); its pre-send check refuses a version that is no
longer the current approved letter. ENG-04's Send drafts through `engagements.api`'s sender port,
which this module fills (`send_letter`). §7216 consents travel in their own `consent_set`
envelope (T-01), never inside the letter (AC-15).

**G3.** The engagement-letter gate is met only by (a) a completed, non-superseded letter envelope
carrying a client signature and a firm countersignature, (b) a completed, non-superseded
record-mode letter import, or (c) a letter recorded through `letter.record` (engagements' own
record, kept as the third source). P-07's interim provider is replaced through
`engagements.api.replace_gate_provider`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.modules.engagements.api import (
    GateFact,
    letter_for_envelope,
    letter_send_problems,
    recorded_letter,
    register_letter_envelope_status,
    register_letter_sender,
    replace_gate_provider,
)
from abacus.modules.identity.api import AuthContext

LETTER: Final = "engagement_letter"
CONTRACTED: Final = frozenset({"consent_set", "tax_return"})  # consumers.SOURCE_CONTRACTS
LETTER_GATE: Final = "G3"


@dataclass(frozen=True)
class SourceDocument:
    """One document a source prefills: an evidence version or a generated document's version,
    by its bytes' SHA-256."""

    sha256: str
    evidence_version_id: UUID | None = None
    generated_document_version_id: UUID | None = None
    page_count: int | None = None
    signer_visible: bool = True
    read_only: bool = False
    watermark: str | None = None
    source_ref: str | None = None
    placement: str = "anchors"
    tri: bool = False


@dataclass(frozen=True)
class SourceSigner:
    """One signer a source prefills: a client contact or a firm member."""

    identity_method: str
    contact_id: UUID | None = None
    user_id: UUID | None = None
    role: str = "signer"
    routing_group: int = 1


@dataclass(frozen=True)
class SourceDraft:
    """What a source prefills for a draft from one of its records (N-02-T20). The source has
    authorised the caller on its record; the builder authorises `envelope.draft` again."""

    purpose: str
    policy_family: str
    client_id: UUID
    title: str
    documents: tuple[SourceDocument, ...]
    signers: tuple[SourceSigner, ...]
    form_code: str | None = None
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None
    signer_order: str = "sequential"


DraftProvider = Callable[[AuthContext, UUID], Awaitable[SourceDraft]]
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
    # N-02-T20: the draft prefill; None until the source can draft (the letter: N-02-T32).
    draft: DraftProvider | None = None


_SOURCES: dict[str, EnvelopeSource] = {}


def register_envelope_source(source: EnvelopeSource) -> None:
    """A source registers once, at import; the same source again (a reload) replaces itself."""
    known = _SOURCES.get(source.kind)
    if known is not None and known != source:
        raise RuntimeError(f"envelope source {source.kind!r} is already registered")
    if source.kind in CONTRACTED and source.draft is None:
        # C7 v1.1 (N-02-T25): `consent_set` and `tax_return` sources must be able to draft.
        raise RuntimeError(f"envelope source {source.kind!r} must provide a draft")
    _SOURCES[source.kind] = source


def envelope_source(kind: str) -> EnvelopeSource:
    """The registered source, or `unknown_envelope_source` (fail closed)."""
    found = _SOURCES.get(kind)
    if found is None:
        raise UnknownEnvelopeSource(facts={"kind": kind})
    return found


def registered_sources() -> frozenset[str]:
    return frozenset(_SOURCES)


async def _letter_draft(ctx: AuthContext, version_id: UUID) -> SourceDraft:
    """The approved letter version's prefill (N-02-T33)."""
    letter = await letter_for_envelope(ctx, version_id)
    return SourceDraft(
        purpose=LETTER,
        policy_family=LETTER,
        client_id=letter.client_id,
        title=letter.title,
        documents=(
            SourceDocument(
                sha256=letter.content_hash,
                generated_document_version_id=letter.generated_document_version_id,
                source_ref=f"engagement_letter_version:{version_id}",
            ),
        ),
        signers=(
            SourceSigner(identity_method="email_code", contact_id=letter.client_signer_contact_id),
            SourceSigner(
                identity_method="firm_sso",
                user_id=letter.countersigner_user_id,
                role="countersigner",
                routing_group=2,
            ),
        ),
        engagement_id=letter.engagement_id,
    )


async def _letter_documents(ctx: AuthContext, version_id: UUID) -> Sequence[object]:
    return (await _letter_draft(ctx, version_id)).documents


async def _letter_signers(ctx: AuthContext, version_id: UUID) -> Sequence[object]:
    return (await _letter_draft(ctx, version_id)).signers


async def send_letter(ctx: AuthContext, version_id: UUID) -> UUID:
    """ENG-04's Send: a C7 draft from the approved letter version, for SIG-02."""
    from abacus.modules.signatures.builder import create_draft

    return await create_draft(ctx, LETTER, version_id)


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


_COMPLETED_AT = text("SELECT completed_at FROM envelopes WHERE id = :id")


async def letter_signed_at(tenant: TenantContext, engagement_id: UUID) -> datetime | None:
    """T-01-T51 (POR-02 Earlier): when the engagement's G3 letter envelope completed, or None."""
    envelope_id = await letter_envelope(tenant, engagement_id)
    if envelope_id is None:
        return None
    async with tenant_session(tenant) as session:
        return await session.scalar(_COMPLETED_AT, {"id": envelope_id})


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
            checks=(letter_send_problems,),
            completed_label="Signed",
            draft=_letter_draft,
        )
    )
    replace_gate_provider(LETTER_GATE, letter_gate)
    register_letter_sender(send_letter)
    register_letter_envelope_status(envelope_status)


async def envelope_status(tenant: TenantContext, envelope_id: UUID) -> str | None:
    """N-02-T35: a letter envelope's C7 status; `superseded` once superseded."""
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text("SELECT status, superseded_at FROM envelopes WHERE id = :id"),
                {"id": envelope_id},
            )
        ).first()
    if row is None:
        return None
    return "superseded" if row.superseded_at is not None else str(row.status)
