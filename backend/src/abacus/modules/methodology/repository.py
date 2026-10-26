"""Methodology data access (ADR-008, ADR-103): only this module's tables."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID, uuid4

from sqlalchemy import Date, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from abacus.modules.methodology.models import (
    MethodologyAccountRule,
    MethodologyArea,
    MethodologyRequestItem,
    MethodologyTemplate,
    MethodologyVersion,
    MethodologyVersionEvent,
    MethodologyVersionState,
)
from abacus.modules.methodology.workbook import Methodology


async def template_id_for(session: AsyncSession, name: str) -> UUID | None:
    return (
        await session.execute(
            select(MethodologyTemplate.id).where(MethodologyTemplate.name == name)
        )
    ).scalar_one_or_none()


async def lock_or_insert_template(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    name: str,
    created_by: UUID,
    engagement_types: Sequence[str] = ("fs_audit",),
) -> tuple[UUID, bool]:
    """The template's ID, created if new; locked, so concurrent imports number versions in turn."""
    created = (
        await session.execute(
            pg_insert(MethodologyTemplate)
            .values(
                id=uuid4(),
                tenant_id=tenant_id,
                name=name,
                created_by=created_by,
                engagement_types=list(engagement_types),
            )
            .on_conflict_do_nothing(index_elements=["tenant_id", "name"])
            .returning(MethodologyTemplate.id)
        )
    ).scalar_one_or_none()
    if created is not None:
        return created, True
    existing = (
        await session.execute(
            select(MethodologyTemplate.id).where(MethodologyTemplate.name == name)
        )
    ).scalar_one()
    # Serialise version numbering per template until commit. Not `FOR UPDATE`: that needs UPDATE
    # privilege, and templates are insert-only for the app (ADR-004).
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(str(existing), 0)))
    )
    return existing, False


async def lock_template(session: AsyncSession, template_id: UUID) -> int:
    """Lock an existing template's version numbering (as an import does) and return its latest
    version number (TASK-074: drafted guidance publishes onto the latest only)."""
    await session.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended(str(template_id), 0)))
    )
    latest = await session.scalar(
        select(func.max(MethodologyVersion.version)).where(
            MethodologyVersion.template_id == template_id
        )
    )
    return latest or 0


async def insert_version(
    session: AsyncSession,
    *,
    tenant_id: UUID,
    template_id: UUID,
    fingerprint: str,
    imported_by: UUID,
    methodology: Methodology,
    origin: str = "workbook",
    drafted_from_version_id: UUID | None = None,
) -> tuple[UUID, int]:
    """The next version of the template with its rows (the caller holds the template's lock), and
    its lifecycle row (K-01-T02): until `methodology.lifecycle` turns on approval (K-01-T06) a new
    version is published on its own authority (`legacy_import`) and becomes the template's
    default for new engagements, as the newest version always was."""
    latest = await session.scalar(
        select(func.max(MethodologyVersion.version)).where(
            MethodologyVersion.template_id == template_id
        )
    )
    number = (latest or 0) + 1
    version_id = uuid4()
    await session.execute(
        insert(MethodologyVersion).values(
            id=version_id,
            tenant_id=tenant_id,
            template_id=template_id,
            version=number,
            source_fingerprint=fingerprint,
            imported_by=imported_by,
            label=f"v{number}",
            origin=origin,
            drafted_from_version_id=drafted_from_version_id,
        )
    )
    base = {"tenant_id": tenant_id, "version_id": version_id}
    await session.execute(
        insert(MethodologyArea),
        [
            {**base, "code": a.code, "name": a.name, "position": i}
            for i, a in enumerate(methodology.areas)
        ],
    )
    if methodology.items:
        await session.execute(
            insert(MethodologyRequestItem),
            [
                {
                    **base,
                    "area_code": t.area_code,
                    "description": t.description,
                    "retrievability_tier": t.tier,
                    "position": i,
                    "why": t.why,
                    "good_looks_like": t.good_looks_like,
                    "blocks_fieldwork": t.blocks_fieldwork,
                    "effort": t.effort,
                    "guidance_source": t.guidance_source,
                    "guidance_approved_by": t.guidance_approved_by,
                }
                for i, t in enumerate(methodology.items)
            ],
        )
    if methodology.rules:
        await session.execute(
            insert(MethodologyAccountRule),
            [
                {
                    **base,
                    "area_code": r.area_code,
                    "account_from": r.account_from,
                    "account_to": r.account_to,
                    "position": i,
                }
                for i, r in enumerate(methodology.rules)
            ],
        )
    await _publish_as_legacy(session, tenant_id, template_id, version_id, imported_by, origin)
    return version_id, number


async def _publish_as_legacy(
    session: AsyncSession,
    tenant_id: UUID,
    template_id: UUID,
    version_id: UUID,
    actor: UUID,
    origin: str,
) -> None:
    types = (
        await session.execute(
            select(MethodologyTemplate.engagement_types).where(
                MethodologyTemplate.id == template_id
            )
        )
    ).scalar_one()
    await session.execute(
        update(MethodologyVersionState)
        .where(
            MethodologyVersionState.template_id == template_id,
            MethodologyVersionState.default_for_new_engagements.is_(True),
        )
        .values(
            default_for_new_engagements=False,
            row_version=MethodologyVersionState.row_version + 1,
        )
    )
    await session.execute(
        insert(MethodologyVersionState).values(
            tenant_id=tenant_id,
            version_id=version_id,
            template_id=template_id,
            status="published",
            effective_from=func.abacus_now().cast(Date),
            approval_basis="legacy_import",
            engagement_types=list(types),
            default_for_new_engagements=True,
            row_version=1,
        )
    )
    await session.execute(
        insert(MethodologyVersionEvent).values(
            tenant_id=tenant_id,
            version_id=version_id,
            kind="imported" if origin == "workbook" else "published",
            actor_user_id=actor,
            facts={"origin": origin},
        )
    )


async def list_templates(
    session: AsyncSession, *, latest: bool = False
) -> Sequence[tuple[MethodologyTemplate, MethodologyVersion]]:
    """Every template of the firm with each of its versions, newest first; with `latest`, only
    each template's newest version (SPEC-025 AC-3; TASK-047 D3)."""
    query = (
        select(MethodologyTemplate, MethodologyVersion)
        .join(MethodologyVersion, MethodologyVersion.template_id == MethodologyTemplate.id)
        .order_by(MethodologyTemplate.name, MethodologyVersion.version.desc())
    )
    if latest:
        newer = aliased(MethodologyVersion)
        query = query.where(
            ~select(newer.id)
            .where(
                newer.template_id == MethodologyVersion.template_id,
                newer.version > MethodologyVersion.version,
            )
            .exists()
        )
    rows = await session.execute(query)
    return [(t, v) for t, v in rows.all()]


async def get_version(
    session: AsyncSession, version_id: UUID
) -> tuple[MethodologyTemplate, MethodologyVersion] | None:
    row = (
        await session.execute(
            select(MethodologyTemplate, MethodologyVersion)
            .join(MethodologyVersion, MethodologyVersion.template_id == MethodologyTemplate.id)
            .where(MethodologyVersion.id == version_id)
        )
    ).first()
    return (row[0], row[1]) if row is not None else None


async def version_rows(
    session: AsyncSession, version_id: UUID
) -> tuple[
    Sequence[MethodologyArea], Sequence[MethodologyRequestItem], Sequence[MethodologyAccountRule]
]:
    areas = (
        await session.execute(
            select(MethodologyArea)
            .where(MethodologyArea.version_id == version_id)
            .order_by(MethodologyArea.position)
        )
    ).scalars()
    items = (
        await session.execute(
            select(MethodologyRequestItem)
            .where(MethodologyRequestItem.version_id == version_id)
            .order_by(MethodologyRequestItem.position)
        )
    ).scalars()
    rules = (
        await session.execute(
            select(MethodologyAccountRule)
            .where(MethodologyAccountRule.version_id == version_id)
            .order_by(MethodologyAccountRule.position)
        )
    ).scalars()
    return areas.all(), items.all(), rules.all()


async def template_count(session: AsyncSession) -> int:
    """How many methodology templates the session's firm has (SPEC-024 AC-7)."""
    return int(await session.scalar(select(func.count()).select_from(MethodologyTemplate)) or 0)
