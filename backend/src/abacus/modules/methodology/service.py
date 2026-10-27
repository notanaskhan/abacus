"""Methodology templates and versions (SPEC-008; SPEC-031, SPEC-035; K-01-T02 re-owned them from
engagements). A template's versions are insert-only; a workbook import or a drafted-guidance
publish writes the next one, and every version has a lifecycle row (`methodology_version_states`)
and insert-only events. Until `methodology.lifecycle` (K-01-T06), a new version is published on
import, as before, with `approval_basis = legacy_import`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._flags import METHODOLOGY_LIFECYCLE, METHODOLOGY_PROGRAMS
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.methodology.models import MethodologyTemplate, MethodologyVersion
from abacus.modules.methodology.repository import (
    get_version,
    insert_version,
    list_templates,
    lock_or_insert_template,
    lock_template,
    template_count,
    version_rows,
)
from abacus.modules.methodology.workbook import (
    AccountRule,
    Area,
    Effort,
    Methodology,
    TemplateItem,
    Tier,
    parse_workbook,
)

# F-03-T12 (migration 0069): the 14 engagement types; `audit` became `fs_audit` (no alias).
# DEC-19: single_audit and yellow_book stay out. Defined here since K-01-T02 because a template
# names the types it serves and `methodology` sits below `engagements` (DEC-407).
EngagementType = Literal[
    "fs_audit",
    "ebp_audit",
    "review",
    "compilation",
    "preparation",
    "agreed_upon_procedures",
    "soc1",
    "soc2",
    "readiness",
    "internal_audit",
    "tax_compliance",
    "cas_monthly_close",
    "notice_response",
    "advisory",
]


class TemplateNameInvalid(DomainInvalid):
    """A template name is 1 to 100 characters."""

    code = "template_name_invalid"


@dataclass(frozen=True)
class TemplateVersionSummary:
    template_id: UUID
    template_name: str
    version_id: UUID
    version: int
    created_at: datetime
    engagement_types: tuple[str, ...] = ("fs_audit",)


@dataclass(frozen=True)
class MethodologyVersionView:
    summary: TemplateVersionSummary
    areas: tuple[Area, ...]
    items: tuple[TemplateItem, ...]
    rules: tuple[AccountRule, ...]


def _summary(template: MethodologyTemplate, version: MethodologyVersion) -> TemplateVersionSummary:
    return TemplateVersionSummary(
        template.id,
        template.name,
        version.id,
        version.version,
        version.created_at,
        tuple(template.engagement_types),
    )


Family = Literal["ebp", "fs", "ssars"]


async def import_template(
    ctx: AuthContext,
    name: str,
    data: bytes,
    engagement_types: Sequence[EngagementType] = ("fs_audit",),
    family: Family | None = None,
) -> TemplateVersionSummary:
    """Parse and store the workbook as the template's next version (AC-1 to AC-3). Raises
    `TemplateInvalid` with every problem, storing nothing. K-01-T05: with `methodology.programs`
    on, the workbook's Programs and Steps sheets come too; with `methodology.lifecycle` on, the
    version lands in Needs review for a person to approve (K-01-T06) instead of being published
    on import. `family` (EBP, FS, SSARS) is set with a new template only."""
    await authorise(ctx, "methodology.manage", Resource.firm(ctx.tenant_id))
    name = name.strip()
    if not 1 <= len(name) <= 100:
        raise TemplateNameInvalid(name)
    programs = await flag_enabled(ctx.tenant, METHODOLOGY_PROGRAMS)
    for_review = await flag_enabled(ctx.tenant, METHODOLOGY_LIFECYCLE)
    methodology = parse_workbook(data, programs=programs)
    fingerprint = hashlib.sha256(data).hexdigest()
    async with uow(ctx.tenant) as tx:
        template_id, _ = await lock_or_insert_template(
            tx.session,
            tenant_id=ctx.tenant_id,
            name=name,
            created_by=ctx.user_id,
            engagement_types=sorted(set(engagement_types)) or ["fs_audit"],
            family=family,
        )
        version_id, number = await insert_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            template_id=template_id,
            fingerprint=fingerprint,
            imported_by=ctx.user_id,
            methodology=methodology,
            for_review=for_review,
        )
        tx.record(
            "methodology.imported",
            target=Target("methodology_version", version_id),
            after=Ref(
                template_id=template_id,
                version=number,
                source_fingerprint=fingerprint,
                areas=len(methodology.areas),
                items=len(methodology.items),
                rules=len(methodology.rules),
                programs=len(methodology.programs),
                steps=len(methodology.steps),
                status="needs_review" if for_review else "published",
            ),
        )
    found = await version_detail(ctx.tenant, version_id)
    return found.summary


async def methodology_templates(
    ctx: AuthContext, *, latest: bool = False
) -> list[TemplateVersionSummary]:
    await authorise(ctx, "methodology.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        return [_summary(t, v) for t, v in await list_templates(session, latest=latest)]


async def methodology_version(ctx: AuthContext, version_id: UUID) -> MethodologyVersionView:
    await authorise(ctx, "methodology.read", Resource.firm(ctx.tenant_id))
    return await version_detail(ctx.tenant, version_id)


async def version_detail(tenant: TenantContext, version_id: UUID) -> MethodologyVersionView:
    """A version's rows for a caller that has authorised under its own context (`NotFound`
    outside the tenant)."""
    async with tenant_session(tenant) as session:
        return await _detail(session, version_id)


async def _detail(session: AsyncSession, version_id: UUID) -> MethodologyVersionView:
    found = await get_version(session, version_id)
    if found is None:
        raise NotFound("methodology_version")
    areas, items, rules = await version_rows(session, version_id)
    return MethodologyVersionView(
        _summary(*found),
        tuple(Area(a.code, a.name) for a in areas),
        tuple(
            TemplateItem(
                i.area_code,
                i.description,
                cast(Tier, i.retrievability_tier),
                i.why,
                i.good_looks_like,
                i.blocks_fieldwork,
                cast(Effort | None, i.effort),
                i.guidance_source,
                i.guidance_approved_by,
            )
            for i in items
        ),
        tuple(AccountRule(r.area_code, r.account_from, r.account_to) for r in rules),
    )


class VersionNotLatest(DomainConflict):
    """Drafted guidance is published onto the template's latest version only (TASK-074 D2)."""

    code = "version_not_latest"


@dataclass(frozen=True)
class ApprovedGuidance:
    """A template item's approved drafted guidance (SPEC-035 Q3), by its position."""

    position: int
    why: str
    good_looks_like: str
    effort: Effort | None
    blocks_fieldwork: bool
    approved_by: UUID


async def publish_drafted_version(
    tx: UnitOfWork, ctx: AuthContext, version_id: UUID, approved: Sequence[ApprovedGuidance]
) -> TemplateVersionSummary:
    """TASK-074 D2: inside the caller's unit of work, the template's next version: a copy of
    `version_id` (which must be the latest) with the approved guidance on its items, marked
    `drafted` with who approved. Older versions, and engagements pinned to them, are unchanged."""
    await authorise(ctx, "methodology.manage", Resource.firm(ctx.tenant_id))
    detail = await _detail(tx.session, version_id)
    if await lock_template(tx.session, detail.summary.template_id) != detail.summary.version:
        raise VersionNotLatest(str(version_id))
    by_position = {a.position: a for a in approved}
    items = tuple(
        TemplateItem(
            t.area_code,
            t.description,
            t.tier,
            a.why,
            a.good_looks_like,
            a.blocks_fieldwork,
            a.effort,
            "drafted",
            a.approved_by,
        )
        if (a := by_position.get(i)) is not None
        else t
        for i, t in enumerate(detail.items)
    )
    fingerprint = hashlib.sha256(
        repr(
            (str(version_id), sorted((a.position, a.why, a.good_looks_like) for a in approved))
        ).encode()
    ).hexdigest()
    new_id, number = await insert_version(
        tx.session,
        tenant_id=ctx.tenant_id,
        template_id=detail.summary.template_id,
        fingerprint=fingerprint,
        imported_by=ctx.user_id,
        methodology=Methodology(detail.areas, items, detail.rules),
        origin="guidance_draft",
        drafted_from_version_id=version_id,
    )
    tx.record(
        "methodology.published",
        target=Target("methodology_version", new_id),
        after=Ref(
            template_id=detail.summary.template_id,
            version=number,
            from_version_id=version_id,  # the event itself says it's drafted guidance
            drafted_items=len(by_position),
        ),
    )
    return (await _detail(tx.session, new_id)).summary


async def version_in(session: AsyncSession, version_id: UUID) -> MethodologyVersionView:
    """A version's rows inside the caller's unit of work (engagements' pin; `NotFound` outside
    the tenant)."""
    return await _detail(session, version_id)


async def latest_versions(tenant: TenantContext) -> list[TemplateVersionSummary]:
    """Each template's newest version, for a caller that has authorised under its own context
    (roll-forward's "the template's latest")."""
    async with tenant_session(tenant) as session:
        return [_summary(t, v) for t, v in await list_templates(session, latest=True)]


async def templates_in_firm(tenant: TenantContext) -> int:
    """How many templates the firm has (SPEC-024 AC-7, onboarding's methodology step)."""
    async with tenant_session(tenant) as session:
        return await template_count(session)
