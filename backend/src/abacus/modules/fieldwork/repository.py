"""Fieldwork data access (SPEC-037; TASK-077). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.modules.fieldwork.models import (
    EngagementMateriality,
    FieldworkSettings,
    PopulationRow,
    Procedure,
    SelectedItem,
    SelectionRow,
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
