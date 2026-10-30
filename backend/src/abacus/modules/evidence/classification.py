"""Classifying a received document by rule, and what other modules ask of classifications
(N-01-T17; N-01 §3.4; DEC-1177). PROTECTED.

`classify_intake` reads an intake attachment's word layer (the first pages' text) and its
detected TIN last fours (P-03's code-only PII scan; never a sealed value), runs `classifier`, and
inserts one `document_classifications` row (`proposed_by_kind = rule`) in an audited unit of work.
Text never leaves this function and is never logged; the result carries the classification's
fields, not the words.

`filed_classification_match` and `version_with_fingerprint` answer communications' flag checks
(`possible_replacement`, `duplicate_hash`) for one client: a filed version's id, never its
content.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from uuid import UUID

from sqlalchemy import insert, select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence.classifier import Classification, classify
from abacus.modules.evidence.models import (
    DocumentClassification,
    EvidenceItem,
    EvidenceVersion,
)
from abacus.modules.evidence.repository import pages_of, pii_regions_of
from abacus.modules.evidence.words import WORDS_VERSION, read_page_layer

_TEXT_PAGES: Final = 2
# The taxpayer's number first (a W-2's employee SSN over its employer EIN).
_TIN_ORDER: Final = {"ssn": 0, "itin": 0, "ein": 1}
PDF: Final = "application/pdf"


@dataclass(frozen=True)
class ClassifiedIntake:
    """One attachment's rule classification and the reading facts its flags need."""

    classification_id: UUID
    classification: Classification
    has_text_layer: bool
    tin_last4s: tuple[str, ...]


async def classify_intake(
    tenant: TenantContext, attachment_id: UUID, *, file_name: str, media_type: str
) -> ClassifiedIntake:
    """Classify the attachment by rule and record it (a new row each run)."""
    async with tenant_session(tenant) as session:
        pages = await pages_of(
            session, inbox_attachment_id=attachment_id, extractor_version=WORDS_VERSION
        )
        regions = await pii_regions_of(session, inbox_attachment_id=attachment_id)
    texts = [
        " ".join(w.text for w in (await read_page_layer(tenant.tenant_id, page)).words)
        for page in pages[:_TEXT_PAGES]
        if page.has_text_layer
    ]
    tins = sorted(
        (r for r in regions if r.kind in _TIN_ORDER and r.last4 and len(r.last4) == 4),
        key=lambda r: (_TIN_ORDER[r.kind], r.page_no),
    )
    last4s = tuple(dict.fromkeys(r.last4 for r in tins if r.last4))
    page_count = len(pages) if pages else (1 if media_type.startswith("image/") else 0)
    found = classify(file_name, texts, page_count=page_count, tin_last4s=list(last4s))
    async with uow(tenant) as tx:
        classification_id = (
            await tx.session.execute(
                insert(DocumentClassification)
                .values(
                    tenant_id=tenant.tenant_id,
                    subject_kind="inbox_attachment",
                    subject_id=attachment_id,
                    form_family=found.form_family,
                    form_code=found.form_code,
                    tax_year=found.tax_year,
                    kind=found.kind,
                    page_count=found.page_count,
                    taxpayer_tin_last4=found.taxpayer_tin_last4,
                    corrected=found.corrected,
                    confidences=found.confidences,
                    proposed_by_kind="rule",
                    rules_version=found.rules_version,
                )
                .returning(DocumentClassification.id)
            )
        ).scalar_one()
        tx.record(
            "document.classified",
            target=Target("inbox_attachment", attachment_id),
            after=Ref(classification_id=classification_id, pages=found.page_count),
        )
    return ClassifiedIntake(classification_id, found, any(p.has_text_layer for p in pages), last4s)


async def filed_classification_match(
    tenant: TenantContext,
    client_id: UUID,
    *,
    form_family: str,
    tax_year: int,
    issuer_name: str | None,
) -> UUID | None:
    """The client's latest filed version classified as the same family and tax year (and
    issuer, when both name one), for `possible_replacement`; None when there is none."""
    query = (
        select(EvidenceVersion.id)
        .join(
            DocumentClassification,
            (DocumentClassification.subject_kind == "evidence_version")
            & (DocumentClassification.subject_id == EvidenceVersion.id),
        )
        .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
        .where(
            EvidenceItem.client_id == client_id,
            DocumentClassification.form_family == form_family,
            DocumentClassification.tax_year == tax_year,
        )
        .order_by(EvidenceVersion.created_at.desc())
        .limit(1)
    )
    if issuer_name is not None:
        query = query.where(
            (DocumentClassification.issuer_name.is_(None))
            | (DocumentClassification.issuer_name == issuer_name)
        )
    async with tenant_session(tenant) as session:
        return await session.scalar(query)


async def version_with_fingerprint(
    tenant: TenantContext, client_id: UUID, fingerprint: str
) -> UUID | None:
    """The client's earliest version with these exact bytes (SHA-256), for `duplicate_hash`."""
    async with tenant_session(tenant) as session:
        return await session.scalar(
            select(EvidenceVersion.id)
            .join(EvidenceItem, EvidenceItem.id == EvidenceVersion.evidence_item_id)
            .where(EvidenceItem.client_id == client_id, EvidenceVersion.fingerprint == fingerprint)
            .order_by(EvidenceVersion.created_at)
            .limit(1)
        )
