"""Evidence read tools for the Accrued Agent (P-10-T28; C17; ADR-233, ADR-049, ADR-050, ADR-052).

Declared as `ToolDecl` records (`kernel.agent_tools`) and registered by `agents`. The runtime has
authorised `evidence.read` on the engagement (or the run's); each handler reads that engagement's
rows only. File names and what an extraction read off a client's document are client content:
untrusted, wrapped for the model. Amounts are the extraction's own figures; differences are
computed here (ADR-050).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select

from abacus.kernel.agent_tools import MAX_ROWS, ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.evidence.models import EvidenceItem, EvidenceVersion, UploadExtraction

Int = classified("internal")
Conf = classified("confidential")
READ: Final = "evidence.read"


def _engagement(caller: ToolCaller, named: UUID | None) -> UUID:
    found = named or caller.engagement_id
    if found is None:
        raise NotFound("engagement")
    return found


class SearchIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None
    text: Annotated[str, Field(min_length=2, max_length=80), Conf]


class UploadsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None
    since: Annotated[datetime | None, Int] = None


class ExtractionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None
    evidence_version_id: Annotated[UUID, Int]


class EvidenceRow(BaseModel):
    id: Annotated[UUID, Int]  # the evidence item
    title: Annotated[str, Conf]
    folder_kind: Annotated[str, Int]
    created_at: Annotated[datetime, Int]


class SearchOut(BaseModel):
    items: Annotated[list[EvidenceRow], Field(max_length=MAX_ROWS), Int]
    total: Annotated[int, Field(ge=0), Int]


class UploadRow(BaseModel):
    id: Annotated[UUID, Int]  # the version
    evidence_item_id: Annotated[UUID, Int]
    version_no: Annotated[int, Int]
    display_name: Annotated[str | None, Conf] = None
    media_type: Annotated[str, Int]
    size_bytes: Annotated[int, Int]
    source: Annotated[str, Int]
    period_end: Annotated[date | None, Int] = None
    created_at: Annotated[datetime, Int]


class UploadsOut(BaseModel):
    uploads: Annotated[list[UploadRow], Field(max_length=MAX_ROWS), Int]
    total: Annotated[int, Field(ge=0), Int]
    total_bytes: Annotated[int, Field(ge=0), Int]


class ExtractionOut(BaseModel):
    evidence_version_id: Annotated[UUID, Int]
    status: Annotated[str, Int]
    extractor_version: Annotated[str, Int]
    page_count: Annotated[int | None, Int] = None
    truncated: Annotated[bool, Int]
    period_start: Annotated[date | None, Int] = None
    period_end: Annotated[date | None, Int] = None
    as_of: Annotated[date | None, Int] = None
    entity_name: Annotated[str | None, Conf] = None
    account_last4: Annotated[str | None, Conf] = None
    opening: Annotated[Decimal | None, Conf] = None
    closing: Annotated[Decimal | None, Conf] = None
    credits: Annotated[Decimal | None, Conf] = None
    debits: Annotated[Decimal | None, Conf] = None
    # Opening + credits - debits - closing, by code; None when a figure is missing.
    roll_forward_difference: Annotated[Decimal | None, Conf] = None


async def search(caller: ToolCaller, args: SearchIn) -> SearchOut:
    """Evidence items whose title holds the text (case-insensitive)."""
    engagement = _engagement(caller, args.engagement_id)
    needle = "%" + args.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    where = (
        EvidenceItem.engagement_id == engagement,
        EvidenceItem.title.ilike(needle, escape="\\"),
    )
    async with tenant_session(caller.tenant) as session:
        total = await session.scalar(select(func.count()).select_from(EvidenceItem).where(*where))
        rows = (
            await session.execute(
                select(EvidenceItem)
                .where(*where)
                .order_by(EvidenceItem.created_at.desc(), EvidenceItem.id)
                .limit(MAX_ROWS)
            )
        ).scalars()
        items = [
            EvidenceRow(id=r.id, title=r.title, folder_kind=r.folder_kind, created_at=r.created_at)
            for r in rows
        ]
    return SearchOut(items=items, total=int(total or 0))


async def list_uploads(caller: ToolCaller, args: UploadsIn) -> UploadsOut:
    engagement = _engagement(caller, args.engagement_id)
    where = [EvidenceVersion.engagement_id == engagement]
    if args.since is not None:
        where.append(EvidenceVersion.created_at >= args.since)
    async with tenant_session(caller.tenant) as session:
        total, size = (
            await session.execute(
                select(func.count(), func.coalesce(func.sum(EvidenceVersion.size_bytes), 0)).where(
                    *where
                )
            )
        ).one()
        rows = (
            await session.execute(
                select(EvidenceVersion)
                .where(*where)
                .order_by(EvidenceVersion.created_at.desc(), EvidenceVersion.id)
                .limit(MAX_ROWS)
            )
        ).scalars()
        uploads = [
            UploadRow(
                id=v.id,
                evidence_item_id=v.evidence_item_id,
                version_no=v.version_no,
                display_name=v.display_name,
                media_type=v.media_type,
                size_bytes=v.size_bytes,
                source=v.source,
                period_end=v.period_end,
                created_at=v.created_at,
            )
            for v in rows
        ]
    return UploadsOut(uploads=uploads, total=int(total), total_bytes=int(size))


def roll_forward(
    opening: Decimal | None,
    credits: Decimal | None,
    debits: Decimal | None,
    closing: Decimal | None,
) -> Decimal | None:
    """A statement's roll-forward check, by code (ADR-050): opening + credits - debits -
    closing."""
    if opening is None or credits is None or debits is None or closing is None:
        return None
    return opening + credits - debits - closing


async def read_extraction(caller: ToolCaller, args: ExtractionIn) -> ExtractionOut:
    engagement = _engagement(caller, args.engagement_id)
    async with tenant_session(caller.tenant) as session:
        found = (
            await session.execute(
                select(UploadExtraction)
                .where(
                    UploadExtraction.evidence_version_id == args.evidence_version_id,
                    or_(UploadExtraction.engagement_id == engagement),
                )
                .order_by(UploadExtraction.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if found is None:
        raise NotFound("upload_extraction")  # none, or another engagement's
    return ExtractionOut(
        evidence_version_id=args.evidence_version_id,
        status=found.status,
        extractor_version=found.extractor_version,
        page_count=found.page_count,
        truncated=found.truncated,
        period_start=found.period_start,
        period_end=found.period_end,
        as_of=found.as_of,
        entity_name=found.entity_name,
        account_last4=found.account_last4,
        opening=found.opening,
        closing=found.closing,
        credits=found.credits,
        debits=found.debits,
        roll_forward_difference=roll_forward(
            found.opening, found.credits, found.debits, found.closing
        ),
    )


AGENT_TOOLS: Final = (
    ToolDecl(
        "evidence.search", "read", READ, "confidential", SearchIn, SearchOut, search,
        records_read="evidence_item",
    ),
    ToolDecl(
        "evidence.read_extraction", "read", READ, "restricted", ExtractionIn, ExtractionOut,
        read_extraction, untrusted=("entity_name",), records_read="upload_extraction",
    ),
    ToolDecl(
        "evidence.list_uploads", "read", READ, "confidential", UploadsIn, UploadsOut,
        list_uploads, records_read="evidence_version",
    ),
)  # fmt: skip
