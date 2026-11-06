"""Reads for a consumer of form extraction (N-04-T07; P-11 F8; DEC-2326): the boxes code read for a
version, the OCR gate's last refusal, and the versions holding the same bytes. Identifiers and
stored values only: the caller authorised on its own record."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.evidence.models import EvidenceVersion


@dataclass(frozen=True)
class ReadField:
    id: UUID
    field_key: str
    value_text: str | None
    last4: str | None
    confidence: Decimal
    low_confidence: bool
    form_type: str
    tax_year: int | None


_FIELDS = text(
    "SELECT DISTINCT ON (field_key) id, field_key, value_text, last4, confidence, low_confidence, "
    "form_type, tax_year FROM extracted_fields WHERE evidence_version_id = :v "
    "ORDER BY field_key, created_at DESC"
)
_REFUSAL = text(
    "SELECT refused_reason FROM ocr_runs WHERE evidence_version_id = :v AND status = 'refused' "
    "ORDER BY created_at DESC LIMIT 1"
)


async def extracted_fields_of(tenant: TenantContext, version_id: UUID) -> tuple[ReadField, ...]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_FIELDS, {"v": version_id})).all()
    return tuple(ReadField(*row) for row in rows)


async def ocr_refusal_of(tenant: TenantContext, version_id: UUID) -> str | None:
    """The gate's latest refusal for the version; a refusal is final (AC7.x), never retried."""
    async with tenant_session(tenant) as session:
        return await session.scalar(_REFUSAL, {"v": version_id})


async def versions_with_same_bytes(tenant: TenantContext, version_id: UUID) -> frozenset[UUID]:
    """Every version in the firm holding this version's exact bytes, itself included."""
    async with tenant_session(tenant) as session:
        fingerprint = await session.scalar(
            select(EvidenceVersion.fingerprint).where(EvidenceVersion.id == version_id)
        )
        if fingerprint is None:
            return frozenset()
        found = await session.scalars(
            select(EvidenceVersion.id).where(EvidenceVersion.fingerprint == fingerprint)
        )
        return frozenset(found)
