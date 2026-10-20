"""Fieldwork data access (SPEC-037; TASK-083). Only this module's tables (ADR-008)."""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import Base
from abacus.modules.fieldwork.models import (
    Adjustment,
    AdjustmentEvent,
    AdjustmentLine,
    EngagementAccount,
    EngagementMateriality,
    FieldworkSettings,
    Finding,
    FindingCommunication,
    FindingSeverity,
    ItemResult,
    ItemSignoff,
    ItemSupportRequest,
    MaterialityDecision,
    Misstatement,
    PopulationRow,
    Procedure,
    ProcedureConclusion,
    ProcedureSessionEvent,
    Representation,
    RepresentationRemoval,
    ReviewNote,
    ReviewNoteEvent,
    Risk,
    RiskApproval,
    RiskVersion,
    SelectedItem,
    SelectionApproval,
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


# --- Results and workpapers (SPEC-037; TASK-084) -----------------------------------------------


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


async def support_request_ids(session: AsyncSession, item_id: UUID) -> list[UUID]:
    """The request items created to ask for one entry's support, oldest first."""
    rows = await session.execute(
        select(ItemSupportRequest.request_item_id)
        .where(ItemSupportRequest.selected_item_id == item_id)
        .order_by(ItemSupportRequest.created_at)
    )
    return list(rows.scalars().all())


# --- Bank and payables accounts (SPEC-038; TASK-086) --------------------------------------------


async def insert_accounts(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(EngagementAccount).values(**values))


async def confirmed_accounts(
    session: AsyncSession, engagement_id: UUID
) -> dict[str, EngagementAccount]:
    """Per role, the newest confirmation (two rows at most; after `authorise` on the
    engagement)."""
    found: dict[str, EngagementAccount] = {}
    for role in ("bank", "payables"):
        row = (
            await session.execute(
                select(EngagementAccount)
                .where(
                    EngagementAccount.engagement_id == engagement_id,
                    EngagementAccount.role == role,
                )
                .order_by(EngagementAccount.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if row is not None:
            found[role] = row
    return found


# --- The flow (SPEC-040; TASK-100) --------------------------------------------------------------


async def approval_of(session: AsyncSession, selection_id: UUID) -> SelectionApproval | None:
    """The selection's approval, if any (one per selection)."""
    return (
        await session.execute(
            select(SelectionApproval).where(SelectionApproval.selection_id == selection_id)
        )
    ).scalar_one_or_none()


async def insert_approval(session: AsyncSession, **values: object) -> bool:
    """False when the selection is already approved."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    made = await session.execute(
        pg_insert(SelectionApproval)
        .values(**values)
        .on_conflict_do_nothing()
        .returning(SelectionApproval.id)
    )
    return made.scalar_one_or_none() is not None


async def signoffs_of(session: AsyncSession, selection_id: UUID) -> Sequence[ItemSignoff]:
    """Every sign-off on the selection's rows, oldest first (LIST_EXEMPT, as above)."""
    return (
        (
            await session.execute(
                select(ItemSignoff)
                .join(SelectedItem, SelectedItem.id == ItemSignoff.selected_item_id)
                .where(SelectedItem.selection_id == selection_id)
                .order_by(ItemSignoff.created_at)
            )
        )
        .scalars()
        .all()
    )


async def insert_signoffs(session: AsyncSession, rows: list[dict[str, object]]) -> int:
    """How many were new (a person signing the same result at the same level again is skipped)."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    if not rows:
        return 0
    made = await session.execute(
        pg_insert(ItemSignoff).values(rows).on_conflict_do_nothing().returning(ItemSignoff.id)
    )
    return len(made.scalars().all())


# --- Review notes (SPEC-041; TASK-103) ----------------------------------------------------------


async def insert_note(session: AsyncSession, **values: object) -> UUID:
    made = await session.execute(insert(ReviewNote).values(**values).returning(ReviewNote.id))
    return made.scalar_one()


async def insert_note_event(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ReviewNoteEvent).values(**values))


async def get_note(session: AsyncSession, note_id: UUID) -> ReviewNote | None:
    return (
        await session.execute(select(ReviewNote).where(ReviewNote.id == note_id))
    ).scalar_one_or_none()


async def notes_of(session: AsyncSession, procedure_id: UUID) -> Sequence[ReviewNote]:
    """The procedure's notes, oldest first (LIST_EXEMPT: one procedure, after `authorise`)."""
    return (
        (
            await session.execute(
                select(ReviewNote)
                .where(ReviewNote.procedure_id == procedure_id)
                .order_by(ReviewNote.created_at)
            )
        )
        .scalars()
        .all()
    )


async def note_events_of(
    session: AsyncSession, note_ids: Sequence[UUID]
) -> Sequence[ReviewNoteEvent]:
    """Those notes' events, oldest first (LIST_EXEMPT, as above)."""
    if not note_ids:
        return []
    return (
        (
            await session.execute(
                select(ReviewNoteEvent)
                .where(ReviewNoteEvent.review_note_id.in_(note_ids))
                .order_by(ReviewNoteEvent.created_at)
            )
        )
        .scalars()
        .all()
    )


# --- Findings (SPEC-043; TASK-107) ---------------------------------------------------------------


async def insert_finding(session: AsyncSession, **values: object) -> UUID:
    made = await session.execute(insert(Finding).values(**values).returning(Finding.id))
    return made.scalar_one()


async def insert_misstatement(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(Misstatement).values(**values))


async def get_finding(session: AsyncSession, finding_id: UUID) -> Finding | None:
    return (
        await session.execute(select(Finding).where(Finding.id == finding_id))
    ).scalar_one_or_none()


async def findings_of(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[Finding]:
    """The engagement's findings, oldest first, through `visible()`."""
    return (
        (
            await session.execute(
                select(Finding)
                .where(
                    Finding.engagement_id == engagement_id,
                    visible(ctx, "procedure.read", Finding.engagement_id),
                )
                .order_by(Finding.created_at)
            )
        )
        .scalars()
        .all()
    )


async def newest_misstatements(
    session: AsyncSession, finding_ids: Sequence[UUID]
) -> dict[UUID, Misstatement]:
    """Per finding, its newest misstatement (LIST_EXEMPT: findings read through `visible()`)."""
    if not finding_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(Misstatement)
                .where(Misstatement.finding_id.in_(finding_ids))
                .ext(distinct_on(Misstatement.finding_id))
                .order_by(Misstatement.finding_id, Misstatement.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {m.finding_id: m for m in rows}


# --- The agent procedure session (SPEC-044; TASK-109) ------------------------------------------


async def insert_session_event(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(ProcedureSessionEvent).values(**values))


async def plan_approval(session: AsyncSession, procedure_id: UUID) -> ProcedureSessionEvent | None:
    return (
        await session.execute(
            select(ProcedureSessionEvent)
            .where(
                ProcedureSessionEvent.procedure_id == procedure_id,
                ProcedureSessionEvent.kind == "plan_approved",
            )
            .order_by(ProcedureSessionEvent.created_at)
            .limit(1)
        )
    ).scalar_one_or_none()


# --- Planning: materiality decisions and the risk register (SPEC-300; TASK-301) ----------------


async def materiality_versions(
    session: AsyncSession, engagement_id: UUID
) -> Sequence[EngagementMateriality]:
    """Every materiality version, newest first (LIST_EXEMPT: read after `procedure.read`)."""
    return (
        (
            await session.execute(
                select(EngagementMateriality)
                .where(EngagementMateriality.engagement_id == engagement_id)
                .order_by(EngagementMateriality.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def materiality_decisions(
    session: AsyncSession, materiality_ids: Sequence[UUID]
) -> dict[UUID, MaterialityDecision]:
    """Per version, its decision (LIST_EXEMPT: versions read after `procedure.read`)."""
    if not materiality_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(MaterialityDecision).where(
                    MaterialityDecision.materiality_id.in_(materiality_ids)
                )
            )
        )
        .scalars()
        .all()
    )
    return {d.materiality_id: d for d in rows}


async def insert_materiality_decision(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(MaterialityDecision).values(**values))


async def risks_of(session: AsyncSession, ctx: AuthContext, engagement_id: UUID) -> Sequence[Risk]:
    """The engagement's risks, R1 first, through `visible()`."""
    return (
        (
            await session.execute(
                select(Risk)
                .where(
                    Risk.engagement_id == engagement_id,
                    visible(ctx, "procedure.read", Risk.engagement_id),
                )
                .order_by(Risk.number)
            )
        )
        .scalars()
        .all()
    )


async def get_risk(session: AsyncSession, risk_id: UUID) -> Risk | None:
    return (await session.execute(select(Risk).where(Risk.id == risk_id))).scalar_one_or_none()


async def next_risk_number(session: AsyncSession, engagement_id: UUID) -> int:
    """Under the engagement's lock (LIST_EXEMPT: a count inside the caller's unit of work)."""
    top = await session.scalar(
        select(func.max(Risk.number)).where(Risk.engagement_id == engagement_id)
    )
    return int(top or 0) + 1


async def insert_risk(session: AsyncSession, **values: object) -> UUID:
    made = await session.execute(insert(Risk).values(**values).returning(Risk.id))
    return made.scalar_one()


async def insert_risk_version(session: AsyncSession, **values: object) -> UUID:
    made = await session.execute(insert(RiskVersion).values(**values).returning(RiskVersion.id))
    return made.scalar_one()


async def newest_risk_versions(
    session: AsyncSession, risk_ids: Sequence[UUID]
) -> dict[UUID, RiskVersion]:
    """Per risk, its newest version (LIST_EXEMPT: risks read through `visible()`)."""
    if not risk_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(RiskVersion)
                .where(RiskVersion.risk_id.in_(risk_ids))
                .ext(distinct_on(RiskVersion.risk_id))
                .order_by(RiskVersion.risk_id, RiskVersion.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return {v.risk_id: v for v in rows}


async def risk_approvals(
    session: AsyncSession, version_ids: Sequence[UUID]
) -> dict[UUID, RiskApproval]:
    """Per version, its approval (LIST_EXEMPT: versions read through `visible()` risks)."""
    if not version_ids:
        return {}
    rows = (
        (
            await session.execute(
                select(RiskApproval).where(RiskApproval.risk_version_id.in_(version_ids))
            )
        )
        .scalars()
        .all()
    )
    return {a.risk_version_id: a for a in rows}


async def insert_risk_approval(session: AsyncSession, **values: object) -> None:
    await session.execute(insert(RiskApproval).values(**values))


# --- Completion: severity, adjustments, representations (SPEC-301; TASK-302) -------------------


async def insert_row(session: AsyncSession, model: type[Base], **values: object) -> UUID:
    made = await session.execute(insert(model).values(**values).returning(model.__table__.c.id))
    return made.scalar_one()


async def severities_of(
    session: AsyncSession, finding_ids: Sequence[UUID]
) -> Sequence[FindingSeverity]:
    """Newest first (LIST_EXEMPT: findings read through `visible()`)."""
    if not finding_ids:
        return []
    return (
        (
            await session.execute(
                select(FindingSeverity)
                .where(FindingSeverity.finding_id.in_(finding_ids))
                .order_by(FindingSeverity.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def communications_of(
    session: AsyncSession, finding_ids: Sequence[UUID]
) -> Sequence[FindingCommunication]:
    """Newest first (LIST_EXEMPT: findings read through `visible()`)."""
    if not finding_ids:
        return []
    return (
        (
            await session.execute(
                select(FindingCommunication)
                .where(FindingCommunication.finding_id.in_(finding_ids))
                .order_by(FindingCommunication.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


async def adjustments_of(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[Adjustment]:
    """The engagement's proposed entries, oldest first, through `visible()`."""
    return (
        (
            await session.execute(
                select(Adjustment)
                .where(
                    Adjustment.engagement_id == engagement_id,
                    visible(ctx, "procedure.read", Adjustment.engagement_id),
                )
                .order_by(Adjustment.created_at)
            )
        )
        .scalars()
        .all()
    )


async def get_adjustment(session: AsyncSession, adjustment_id: UUID) -> Adjustment | None:
    return (
        await session.execute(select(Adjustment).where(Adjustment.id == adjustment_id))
    ).scalar_one_or_none()


async def next_adjustment_number(session: AsyncSession, engagement_id: UUID, kind: str) -> int:
    """Under the engagement's lock."""
    top = await session.scalar(
        select(func.max(Adjustment.number)).where(
            Adjustment.engagement_id == engagement_id, Adjustment.kind == kind
        )
    )
    return int(top or 0) + 1


async def adjustment_lines_of(
    session: AsyncSession, adjustment_ids: Sequence[UUID]
) -> Sequence[AdjustmentLine]:
    """LIST_EXEMPT: adjustments read through `visible()`."""
    if not adjustment_ids:
        return []
    return (
        (
            await session.execute(
                select(AdjustmentLine)
                .where(AdjustmentLine.adjustment_id.in_(adjustment_ids))
                .order_by(AdjustmentLine.adjustment_id, AdjustmentLine.position)
            )
        )
        .scalars()
        .all()
    )


async def adjustment_events_of(
    session: AsyncSession, adjustment_ids: Sequence[UUID]
) -> Sequence[AdjustmentEvent]:
    """LIST_EXEMPT: adjustments read through `visible()`."""
    if not adjustment_ids:
        return []
    return (
        (
            await session.execute(
                select(AdjustmentEvent).where(AdjustmentEvent.adjustment_id.in_(adjustment_ids))
            )
        )
        .scalars()
        .all()
    )


async def representations_of(
    session: AsyncSession, ctx: AuthContext, engagement_id: UUID
) -> Sequence[Representation]:
    """The engagement's representations still on the list, oldest first, through `visible()`."""
    removed = select(RepresentationRemoval.representation_id)
    return (
        (
            await session.execute(
                select(Representation)
                .where(
                    Representation.engagement_id == engagement_id,
                    visible(ctx, "procedure.read", Representation.engagement_id),
                    Representation.id.not_in(removed),
                )
                .order_by(Representation.created_at)
            )
        )
        .scalars()
        .all()
    )


async def get_representation(session: AsyncSession, rep_id: UUID) -> Representation | None:
    return (
        await session.execute(select(Representation).where(Representation.id == rep_id))
    ).scalar_one_or_none()


async def search_findings(
    session: AsyncSession, ctx: AuthContext, pattern: str, limit: int
) -> Sequence[Finding]:
    """SPEC-302 (TASK-303): findings whose title contains the pattern, through `visible()`."""
    return (
        (
            await session.execute(
                select(Finding)
                .where(
                    Finding.title.ilike(pattern, escape="\\"),
                    visible(ctx, "procedure.read", Finding.engagement_id),
                )
                .order_by(Finding.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
