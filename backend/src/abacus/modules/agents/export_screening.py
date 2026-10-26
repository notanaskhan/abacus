"""The engagement export's `screening` section (A-01-T19; SPEC-344 §6, §10; DEC-379, DEC-433).

`provenance/screening.csv`: what screening recorded on the package's files, copied as recorded
and read as the requester (`visible()`): each per-file proposal (the action and its confidence)
and each request batch's code-composed verdict. Identifiers and codes only: the rationale is a
model's free text and stays out. Registered in evidence's slot (`register_export_section`); it
reads, never writes, never calls a model.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from sqlalchemy import or_, select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.agents.models import ScreeningResult
from abacus.modules.evidence.api import (
    SectionFile,
    SectionRequest,
    export_requester,
    export_section_csv,
    included_export_versions,
)
from abacus.modules.identity.api import visible

COLUMNS: Final = (
    "screening_result_id",
    "subject_kind",
    "evidence_version_id",
    "request_item_id",
    "batch_no",
    "action",
    "confidence",
    "verdict",
    "supersedes_id",
    "created_by_kind",
    "created_at",
)


async def screening_section(tenant: TenantContext, request: SectionRequest) -> list[SectionFile]:
    ctx = await export_requester(tenant, request)
    versions = sorted(await included_export_versions(tenant, request))
    found: Sequence[ScreeningResult] = []
    if versions:
        async with tenant_session(ctx.tenant) as session:
            found = (
                (
                    await session.execute(
                        select(ScreeningResult)
                        .where(
                            ScreeningResult.engagement_id == request.engagement_id,
                            or_(
                                (ScreeningResult.subject_kind == "version")
                                & ScreeningResult.evidence_version_id.in_(versions),
                                (ScreeningResult.subject_kind == "request_batch")
                                & ScreeningResult.evidence_version_ids.overlap(versions),
                            ),
                            visible(ctx, "evidence.read", ScreeningResult.engagement_id),
                        )
                        .order_by(ScreeningResult.created_at, ScreeningResult.id)
                    )
                )
                .scalars()
                .all()
            )
    rows = [
        (
            r.id,
            r.subject_kind,
            r.evidence_version_id if r.subject_kind == "version" else "",
            r.request_item_id,
            r.batch_no,
            r.action if r.subject_kind == "version" else "",
            r.confidence if r.subject_kind == "version" else "",
            r.verdict,
            r.supersedes_id,
            r.created_by_kind,
            r.created_at,
        )
        for r in found
    ]
    return [SectionFile("screening.csv", export_section_csv(COLUMNS, rows))]
