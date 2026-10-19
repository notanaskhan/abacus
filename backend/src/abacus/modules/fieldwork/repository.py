"""Fieldwork data access (SPEC-037; TASK-077). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.fieldwork.models import (
    EngagementMateriality,
    FieldworkSettings,
    ItemResult,
    ItemSupportRequest,
    PopulationRow,
    Procedure,
    ProcedureConclusion,
    SelectedItem,
    SelectionRow,
    WorkpaperSignature,
    WorkpaperVersion,
)
from abacus.modules.identity.api import AuthContext, visible


async def newest_materiality(
    session: AsyncSession, engagement_id: UUID
) -> EngagementMateriality | None:
    return (
        await session.execute(
            select(EngagementMateriality)
            .where(EngagementMateriality.engagement_id == engagement_id)
            .order_by(EngagementMateriality.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def insert_materiality(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(EngagementMateriality).values(**values))


async def newest_settings(session: AsyncSession) -> dict[str, object] | None:
    return await session.scalar(
        select(FieldworkSettings.settings).order_by(FieldworkSettings.created_at.desc()).limit(1)
    )


async def insert_settings(
    session: AsyncSession, tenant_id: UUID, settings: dict[str, object], by: UUID
) -> None:
    await session.execute(
        insert(FieldworkSettings).values(tenant_id=tenant_id, settings=settings, set_by=by)
    )


async def list_procedures(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[Procedure]:
    return (
        (
            await session.execute(
                select(Procedure)
                .where(
                    Procedure.engagement_id == engagement_id,
                    visible(ctx, "procedure.read", Procedure.engagement_id),
                )
                .order_by(Procedure.created_at)
            )
        )
        .scalars()
        .all()
    )


async def get_procedure(session: AsyncSession, procedure_id: UUID) -> Procedure | None:
    return (
        await session.execute(select(Procedure).where(Procedure.id == procedure_id))
    ).scalar_one_or_none()


async def lock_procedure(session: AsyncSession, procedure_id: UUID) -> Procedure | None:
    return (
        await session.execute(
            select(Procedure).where(Procedure.id == procedure_id).with_for_update()
        )
    ).scalar_one_or_none()


async def insert_procedure(session: AsyncSession, **values: object) -> UUID | None:
    """The new procedure's ID, or None when the engagement already has this definition."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    procedure_id = uuid4()
    made = await session.execute(
        pg_insert(Procedure)
        .values(id=procedure_id, **values)
        .on_conflict_do_nothing(constraint="procedures_once")
        .returning(Procedure.id)
    )
    return made.scalar_one_or_none()


async def set_procedure(session: AsyncSession, procedure_id: UUID, **values: object) -> None:
    await session.execute(update(Procedure).where(Procedure.id == procedure_id).values(**values))


async def insert_population(session: AsyncSession, **values: object) -> UUID:
    population_id = uuid4()
    await session.execute(insert(PopulationRow).values(id=population_id, **values))
    return population_id


async def insert_selection(session: AsyncSession, **values: object) -> UUID:
    selection_id = uuid4()
    await session.execute(insert(SelectionRow).values(id=selection_id, **values))
    return selection_id


async def insert_items(session: AsyncSession, rows: list[dict[str, object]]) -> None:
    for start in range(0, len(rows), 1000):
        await session.execute(insert(SelectedItem), rows[start : start + 1000])


async def newest_population(session: AsyncSession, procedure_id: UUID) -> PopulationRow | None:
    return (
        await session.execute(
            select(PopulationRow)
            .where(PopulationRow.procedure_id == procedure_id)
            .order_by(PopulationRow.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def newest_selection(session: AsyncSession, procedure_id: UUID) -> SelectionRow | None:
    return (
        await session.execute(
            select(SelectionRow)
            .where(SelectionRow.procedure_id == procedure_id)
            .order_by(SelectionRow.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def selected_items(
    session: AsyncSession, selection_id: UUID, *, offset: int, limit: int
) -> Sequence[SelectedItem]:
    """One selection's entries, in position order, after `authorise(procedure.read)` on its
    engagement (LIST_EXEMPT: the selection is the engagement's)."""
    return (
        (
            await session.execute(
                select(SelectedItem)
                .where(SelectedItem.selection_id == selection_id)
                .order_by(SelectedItem.position)
                .offset(offset)
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )


async def rule_counts(session: AsyncSession, selection_id: UUID) -> dict[str, int]:
    """How many of a selection's entries each rule chose (LIST_EXEMPT, as above)."""
    rule = func.unnest(SelectedItem.rules).label("rule")
    rows = await session.execute(
        select(rule, func.count())
        .select_from(SelectedItem)
        .where(SelectedItem.selection_id == selection_id)
        .group_by(rule)
    )
    return {str(r): int(n) for r, n in rows.tuples().all()}


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


# --- Results and workpapers (SPEC-037; TASK-078) -----------------------------------------------


async def get_item(session: AsyncSession, item_id: UUID) -> SelectedItem | None:
    return (
        await session.execute(select(SelectedItem).where(SelectedItem.id == item_id))
    ).scalar_one_or_none()


async def all_items(session: AsyncSession, selection_id: UUID) -> Sequence[SelectedItem]:
    """Every entry of one selection, for the workpaper (LIST_EXEMPT: after `authorise` on the
    procedure's engagement)."""
    return (
        (
            await session.execute(
                select(SelectedItem)
                .where(SelectedItem.selection_id == selection_id)
                .order_by(SelectedItem.position)
            )
        )
        .scalars()
        .all()
    )


async def insert_result(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ItemResult).values(**values))


async def newest_results(session: AsyncSession, selection_id: UUID) -> dict[UUID, ItemResult]:
    """Per entry of the selection, its newest result (LIST_EXEMPT, as above)."""
    rows = (
        (
            await session.execute(
                select(ItemResult)
                .join(SelectedItem, SelectedItem.id == ItemResult.selected_item_id)
                .where(SelectedItem.selection_id == selection_id)
                .ext(distinct_on(ItemResult.selected_item_id))
                .order_by(ItemResult.selected_item_id, ItemResult.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {r.selected_item_id: r for r in rows}


async def results_by_id(session: AsyncSession, ids: Sequence[UUID]) -> dict[UUID, ItemResult]:
    """A signed version's results (LIST_EXEMPT, as above)."""
    if not ids:
        return {}
    rows = (await session.execute(select(ItemResult).where(ItemResult.id.in_(ids)))).scalars()
    return {r.selected_item_id: r for r in rows.all()}


async def insert_support_request(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ItemSupportRequest).values(**values))


async def support_requested(session: AsyncSession, selection_id: UUID) -> set[UUID]:
    """The selection's entries with a support request (LIST_EXEMPT, as above)."""
    rows = await session.execute(
        select(ItemSupportRequest.selected_item_id)
        .join(SelectedItem, SelectedItem.id == ItemSupportRequest.selected_item_id)
        .where(SelectedItem.selection_id == selection_id)
    )
    return set(rows.scalars().all())


async def insert_conclusion(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ProcedureConclusion).values(**values))


async def newest_conclusion(
    session: AsyncSession, procedure_id: UUID
) -> ProcedureConclusion | None:
    return (
        await session.execute(
            select(ProcedureConclusion)
            .where(ProcedureConclusion.procedure_id == procedure_id)
            .order_by(ProcedureConclusion.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def get_conclusion(session: AsyncSession, conclusion_id: UUID) -> ProcedureConclusion | None:
    return (
        await session.execute(
            select(ProcedureConclusion).where(ProcedureConclusion.id == conclusion_id)
        )
    ).scalar_one_or_none()


async def get_selection(session: AsyncSession, selection_id: UUID) -> SelectionRow | None:
    return (
        await session.execute(select(SelectionRow).where(SelectionRow.id == selection_id))
    ).scalar_one_or_none()


async def get_population(session: AsyncSession, population_id: UUID) -> PopulationRow | None:
    return (
        await session.execute(select(PopulationRow).where(PopulationRow.id == population_id))
    ).scalar_one_or_none()


async def workpaper_versions(
    session: AsyncSession, procedure_id: UUID
) -> Sequence[WorkpaperVersion]:
    """One procedure's versions, oldest first (LIST_EXEMPT, as above)."""
    return (
        (
            await session.execute(
                select(WorkpaperVersion)
                .where(WorkpaperVersion.procedure_id == procedure_id)
                .order_by(WorkpaperVersion.version)
            )
        )
        .scalars()
        .all()
    )


async def insert_version(session: AsyncSession, **values: object) -> UUID:
    version_id = uuid4()
    await session.execute(insert(WorkpaperVersion).values(id=version_id, **values))
    return version_id


async def signatures_of(
    session: AsyncSession, version_ids: Sequence[UUID]
) -> Sequence[WorkpaperSignature]:
    """Signatures on these versions (LIST_EXEMPT, as above)."""
    if not version_ids:
        return []
    return (
        (
            await session.execute(
                select(WorkpaperSignature)
                .where(WorkpaperSignature.workpaper_version_id.in_(version_ids))
                .order_by(WorkpaperSignature.created_at)
            )
        )
        .scalars()
        .all()
    )


async def insert_signature(session: AsyncSession, **values: object) -> bool:
    """False when the version already has this kind of signature."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    made = await session.execute(
        pg_insert(WorkpaperSignature)
        .values(**values)
        .on_conflict_do_nothing()
        .returning(WorkpaperSignature.kind)
    )
    return made.scalar_one_or_none() is not None
