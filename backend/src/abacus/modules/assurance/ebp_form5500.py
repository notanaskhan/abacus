"""EBP-07: the Form 5500 tie-out (A-05-T54; A-05 §3 F9; EBP-07 a-e).

- `record_draft_received`: the draft Form 5500 a person files against Summit's request; a newer
  draft supersedes the older one, and `ebp.form5500.draft_received` starts `Form5500TieOut`.
- `tie_out` (the workflow's activity, code only): every Schedule H line's draft amount against the
  financial statements' amount for the captions the firm maps to it (`ebp_schedule_h_mappings`,
  the newest published taxonomy effective for the plan year), from AUD-20's current statement
  version (`reporting.api.statement_caption_amounts`). Zero ties; any other difference stays
  inconsistent until a person documents its basis (`document_reconciling_item`, which must foot to
  the difference: Note 8's 48,600 = 15,060 + 33,540). Part IV 4a is checked against the late
  deposits on the late-deposit finding (EBP-04): a "No" with late deposits is flagged inconsistent
  (EBP-07e) and returned for a person to raise; the schema keeps "inconsistent" for a row whose
  issue a person raised.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Annotated, ClassVar, Final, cast
from uuid import UUID

from sqlalchemy import text
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.assurance.compute.ebp import form5500 as engine
from abacus.modules.assurance.form5500_workflow import (
    TIEOUT_ID_PREFIX,
    Form5500TieOutWorkflow,
    TieOutCounts,
    TieOutInput,
)
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.reporting.api import statement_caption_amounts

_ACTOR: Final = "assurance.form5500"


class DraftNotTied(DomainConflict):
    code = "form5500_not_tied"


class ReconcilingItemsDoNotFoot(DomainConflict):
    code = "reconciling_items_do_not_foot"


class Form5500DraftReceived(DomainEvent):
    event_type: ClassVar[str] = "ebp.form5500.draft_received"

    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID, classified("internal")]
    draft_id: Annotated[UUID, classified("internal")]


@dataclass(frozen=True)
class TieOutResult:
    lines: tuple[engine.LineTie, ...]
    part_iv: tuple[tuple[str, engine.PartIvResult], ...]

    @property
    def counts(self) -> TieOutCounts:
        kinds = [line.classification for line in self.lines]
        return TieOutCounts(
            kinds.count("tie"),
            kinds.count("reconciling_item"),
            kinds.count("inconsistent"),
            sum(1 for _, result in self.part_iv if result == "inconsistent"),
        )


async def _engagement(ctx: AuthContext, work_item_id: UUID, action: str) -> UUID:
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    return engagement_id


_SUPERSEDE = text(
    "UPDATE ebp_form5500_drafts SET status = 'superseded', version = version + 1, "
    "updated_at = clock_timestamp() WHERE work_item_id = :w AND plan_year = :y "
    "AND status <> 'superseded'"
)
_DRAFT = text(
    """
    INSERT INTO ebp_form5500_drafts (tenant_id, engagement_id, work_item_id, evidence_version_id,
                                     received_at, plan_year, preparer_provider_id, status)
    VALUES (:t, :e, :w, :v, clock_timestamp(), :y, :p, 'received')
    RETURNING id
    """
)


async def record_draft_received(
    ctx: AuthContext,
    work_item_id: UUID,
    evidence_version_id: UUID,
    plan_year: int,
    preparer_provider_id: UUID | None = None,
) -> UUID:
    engagement_id = await _engagement(ctx, work_item_id, "ebp_form5500.key")
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_SUPERSEDE, {"w": work_item_id, "y": plan_year})
        draft_id = (
            await tx.session.execute(
                _DRAFT,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "v": evidence_version_id,
                    "y": plan_year,
                    "p": preparer_provider_id,
                },
            )
        ).scalar_one()
        tx.record(
            "ebp.form5500.draft_received",
            target=Target("ebp_form5500_draft", draft_id),
            after=Ref(evidence_version=evidence_version_id, plan_year=plan_year),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
        tx.emit(
            Form5500DraftReceived(
                engagement_id=engagement_id, work_item_id=work_item_id, draft_id=draft_id
            )
        )
    return cast(UUID, draft_id)


async def on_draft_received(event: OutboxEvent) -> None:
    draft_id = str(event.payload["draft_id"])
    await dispatch(
        Form5500TieOutWorkflow,
        TieOutInput(str(event.tenant_id), draft_id),
        id=f"{TIEOUT_ID_PREFIX}{draft_id}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


_DRAFT_ROW = text(
    "SELECT engagement_id, work_item_id, plan_year, status FROM ebp_form5500_drafts WHERE id = :d"
)
_LINES = text(
    "SELECT id, line_code, f5500_amount, classification, classified_by_kind "
    "FROM ebp_form5500_lines WHERE draft_id = :d ORDER BY line_code"
)
_MAPPING = text(
    """
    SELECT fs_caption_key, schedule_h_line FROM ebp_schedule_h_mappings
     WHERE published_at IS NOT NULL AND effective_plan_year <= :y
       AND version = (SELECT max(version) FROM ebp_schedule_h_mappings
                       WHERE published_at IS NOT NULL AND effective_plan_year <= :y)
    """
)
_PART_IV = text(
    "SELECT question, draft_answer, amount FROM ebp_part_iv_answers WHERE draft_id = :d"
)
_LATE = text(
    "SELECT COALESCE(sum(principal), 0) FROM ebp_late_remittances "
    "WHERE work_item_id = :w AND schedule_h_4a"
)
_SET_LINE = text(
    """
    UPDATE ebp_form5500_lines
       SET fs_amount = :fs, difference = :difference, classification = :kind,
           classified_by_kind = 'code', engine_version = :engine, inputs_hash = :hash,
           version = version + 1, updated_at = clock_timestamp()
     WHERE id = :id
    """
)
_SET_PART_IV = text(
    "UPDATE ebp_part_iv_answers SET result = 'consistent', version = version + 1, "
    "updated_at = clock_timestamp() WHERE draft_id = :d AND question = :q AND result IS NULL"
)
_TIED = text(
    "UPDATE ebp_form5500_drafts SET status = 'tied', version = version + 1, "
    "updated_at = clock_timestamp() WHERE id = :d AND status = 'received'"
)


def compute(
    lines: Sequence[tuple[str, Decimal | None]],
    fs_by_line: dict[str, Decimal],
    answers: Sequence[tuple[str, str | None, Decimal | None]],
    late_total: Decimal,
) -> TieOutResult:
    ties = tuple(engine.classify(code, fs_by_line.get(code), f5500) for code, f5500 in lines)
    part_iv: tuple[tuple[str, engine.PartIvResult], ...] = tuple(
        (question, engine.part_iv_4a(answer, amount, late_total))
        for question, answer, amount in answers
        if question == "4a"
    )
    return TieOutResult(ties, part_iv)


async def tie_out(tenant: TenantContext, draft_id: UUID) -> TieOutResult:
    """Code only; a line a person already classified keeps that classification."""
    async with uow(tenant) as tx:
        draft = (await tx.session.execute(_DRAFT_ROW, {"d": draft_id})).first()
        if draft is None or draft.status == "superseded":
            raise NotFound("ebp_form5500_draft")
        rows = (await tx.session.execute(_LINES, {"d": draft_id})).all()
        mapping = {
            str(r.fs_caption_key): str(r.schedule_h_line)
            for r in await tx.session.execute(_MAPPING, {"y": draft.plan_year})
        }
        answers = [
            (str(r.question), r.draft_answer, r.amount)
            for r in await tx.session.execute(_PART_IV, {"d": draft_id})
        ]
        late_total = Decimal(
            (await tx.session.execute(_LATE, {"w": draft.work_item_id})).scalar_one()
        )
    fs_by_line = engine.amounts_by_line(
        await statement_caption_amounts(tenant, draft.work_item_id), mapping
    )
    result = compute(
        [(r.line_code, r.f5500_amount) for r in rows], fs_by_line, answers, late_total
    )
    by_code = {r.line_code: r for r in rows}
    async with uow(tenant) as tx:
        for line in result.lines:
            row = by_code[line.line_code]
            if row.classified_by_kind == "human":
                continue
            await tx.session.execute(
                _SET_LINE,
                {
                    "fs": line.fs_amount,
                    "difference": line.difference,
                    "kind": line.classification,
                    "engine": f"{engine.ENGINE_NAME}@{engine.ENGINE_VERSION}",
                    "hash": line.inputs_hash,
                    "id": row.id,
                },
            )
        for question, outcome in result.part_iv:
            if outcome == "consistent":
                await tx.session.execute(_SET_PART_IV, {"d": draft_id, "q": question})
        await tx.session.execute(_TIED, {"d": draft_id})
        counts = result.counts
        tx.record(
            "ebp.form5500.tieout_computed",
            target=Target("ebp_form5500_draft", draft_id),
            after=Ref(
                ties=counts.ties,
                inconsistent=counts.inconsistent,
                part_iv_inconsistent=counts.part_iv_inconsistent,
            ),
            scope=Scope(engagement_id=draft.engagement_id, work_item_id=draft.work_item_id),
        )
    return result


@activity.defn(name="ebp.form5500_tieout")
async def tie_out_activity(tenant_id: str, draft_id: str) -> TieOutCounts:
    tenant = TenantContext(UUID(tenant_id), "system", _ACTOR)
    return (await tie_out(tenant, UUID(draft_id))).counts


_LINE_FOR = text(
    "SELECT l.id, l.difference, l.work_item_id, l.engagement_id FROM ebp_form5500_lines l "
    "WHERE l.id = :id AND l.work_item_id = :w"
)
_RECONCILE = text(
    """
    UPDATE ebp_form5500_lines
       SET classification = 'reconciling_item', note_ref = :note, classified_by_kind = 'human',
           version = version + 1, updated_at = clock_timestamp()
     WHERE id = :id
    """
)


async def document_reconciling_item(
    ctx: AuthContext, work_item_id: UUID, line_id: UUID, note_ref: str, parts: Sequence[Decimal]
) -> None:
    """A person documents a basis difference (Note 8); its parts must foot to the difference."""
    engagement_id = await _engagement(ctx, work_item_id, "ebp_form5500.key")
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_LINE_FOR, {"id": line_id, "w": work_item_id})).first()
    if row is None:
        raise NotFound("ebp_form5500_line")
    if row.difference is None:
        raise DraftNotTied
    if not engine.sums_to(row.difference, parts):
        raise ReconcilingItemsDoNotFoot(facts={"difference": str(row.difference)})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_RECONCILE, {"note": note_ref[:40], "id": line_id})
        tx.record(
            "ebp.form5500.line_reconciled",
            target=Target("ebp_form5500_line", line_id),
            after=Ref(note=note_ref[:40], parts=len(parts)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )


SUBSCRIPTIONS: Final = {Form5500DraftReceived.event_type: on_draft_received}
WORKFLOWS: Final = {Form5500TieOutWorkflow: "background"}
ACTIVITIES: Final = (tie_out_activity,)
