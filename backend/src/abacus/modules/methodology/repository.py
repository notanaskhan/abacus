"""Methodology data access (ADR-008, ADR-103): only this module's tables."""

from __future__ import annotations

import re
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
    Program,
    ProgramStep,
    ProgramStepPbcLink,
)
from abacus.modules.methodology.workbook import STEP_KEY, Methodology, StepRow


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
    family: str | None = None,
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
                family=family,  # K-01-T05: set once, with the template
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
    for_review: bool = False,
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
    if methodology.programs:
        await _insert_programs(session, tenant_id, template_id, version_id, number, methodology)
    if for_review:
        await _land_for_review(session, tenant_id, template_id, version_id, imported_by, origin)
    else:
        await _publish_as_legacy(session, tenant_id, template_id, version_id, imported_by, origin)
    return version_id, number


async def _land_for_review(
    session: AsyncSession,
    tenant_id: UUID,
    template_id: UUID,
    version_id: UUID,
    actor: UUID,
    origin: str,
) -> None:
    """K-01-T05 (`methodology.lifecycle` on): the version waits in Needs review for a person to
    approve it (K-01-T06); the template's published version and default stay as they are."""
    types = (
        await session.execute(
            select(MethodologyTemplate.engagement_types).where(
                MethodologyTemplate.id == template_id
            )
        )
    ).scalar_one()
    await session.execute(
        insert(MethodologyVersionState).values(
            tenant_id=tenant_id,
            version_id=version_id,
            template_id=template_id,
            status="needs_review",
            engagement_types=list(types),
            default_for_new_engagements=False,
            row_version=1,
        )
    )
    await session.execute(
        insert(MethodologyVersionEvent).values(
            tenant_id=tenant_id,
            version_id=version_id,
            kind="imported",
            actor_user_id=actor,
            facts={"origin": origin, "status": "needs_review"},
        )
    )


def _derived_key(program_code: str, number: int) -> str:
    base = re.sub(r"[^a-z0-9_.-]", "-", program_code.casefold()).strip("-") or "step"
    return f"{base}-{number}"[:80]


async def _prior_keys(
    session: AsyncSession, template_id: UUID, number: int
) -> dict[tuple[str, int], str]:
    """The previous version's step keys by (program code, step number): what an unnamed step
    inherits, so a step keeps its anchor across versions (AC4.4)."""
    prior = await session.scalar(
        select(MethodologyVersion.id).where(
            MethodologyVersion.template_id == template_id,
            MethodologyVersion.version == number - 1,
        )
    )
    if prior is None:
        return {}
    rows = await session.execute(
        select(Program.code, ProgramStep.number, ProgramStep.step_key)
        .join(Program, Program.id == ProgramStep.program_id)
        .where(ProgramStep.version_id == prior)
    )
    return {(code, n): key for code, n, key in rows.all()}


def assign_step_keys(steps: Sequence[StepRow], prior: dict[tuple[str, int], str]) -> list[str]:
    """Stable lineage keys, deterministically: the workbook's `step_id` first (reserved before
    anything else), then the previous version's key for the same program and number, then a key
    derived from the program code and number, made unique with a suffix."""
    keys: list[str | None] = [s.step_id for s in steps]
    taken = {k for k in keys if k is not None}
    for i, step in enumerate(steps):
        if keys[i] is not None:
            continue
        inherited = prior.get((step.program_code, step.number))
        if inherited is not None and inherited not in taken and STEP_KEY.fullmatch(inherited):
            keys[i] = inherited
            taken.add(inherited)
    for i, step in enumerate(steps):
        if keys[i] is not None:
            continue
        candidate = base = _derived_key(step.program_code, step.number)
        suffix = 2
        while candidate in taken:
            candidate = f"{base[:76]}-{suffix}"
            suffix += 1
        keys[i] = candidate
        taken.add(candidate)
    return [k for k in keys if k is not None]


async def _insert_programs(
    session: AsyncSession,
    tenant_id: UUID,
    template_id: UUID,
    version_id: UUID,
    number: int,
    methodology: Methodology,
) -> None:
    """Workbook v2's programs, steps (with their lineage keys) and PBC links, in workbook order.
    Inserted before the version's state row, so the frozen trigger sees a version in the making."""
    program_ids: dict[str, UUID] = {}
    for position, program in enumerate(methodology.programs):
        program_ids[program.code] = (
            await session.execute(
                insert(Program)
                .values(
                    tenant_id=tenant_id,
                    version_id=version_id,
                    code=program.code,
                    name=program.name,
                    position=position,
                )
                .returning(Program.id)
            )
        ).scalar_one()
    keys = assign_step_keys(methodology.steps, await _prior_keys(session, template_id, number))
    links: list[dict[str, object]] = []
    steps: list[dict[str, object]] = []
    for step, key in zip(methodology.steps, keys, strict=True):
        step_id = uuid4()
        steps.append(
            {
                "id": step_id,
                "tenant_id": tenant_id,
                "version_id": version_id,
                "program_id": program_ids[step.program_code],
                "step_key": key,
                "number": step.number,
                "text": step.text,
                "assertions": list(step.assertions),
                "standard_refs": list(step.standard_refs),
                "level": step.level,
                "mandatory": step.mandatory,
                "lock_note": step.lock_note,
                "prepopulates": [],
                "depends_on_step_keys": [],
                "origin": "workbook",
            }
        )
        links += [
            dict[str, object](
                {
                    "tenant_id": tenant_id,
                    "version_id": version_id,
                    "step_id": step_id,
                    "request_position": position,
                }
            )
            for position in step.request_positions
        ]
    if steps:
        await session.execute(insert(ProgramStep), steps)
    if links:
        await session.execute(insert(ProgramStepPbcLink), links)


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
