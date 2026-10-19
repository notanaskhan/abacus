"""Fieldwork: materiality, firm defaults, and procedures (SPEC-037; TASK-077; ADR-117).

People enter materiality (Q3); procedures copy the firm's default criteria into their parameters
when they start, with a seed chosen by code and recorded. Selecting runs in the background
(`ProcedureSelectWorkflow`, D3): the population is built and tied to the reconciled general
ledger, then entries are selected by `sampling`. Nothing here asks a model anything (ADR-050).
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel import _flags
from abacus.kernel.db import tenant_session
from abacus.kernel.dispatch import WorkClass, dispatch, register_work_classes
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import check_facts, get_ref, lock_ref
from abacus.modules.fieldwork.models import Procedure
from abacus.modules.fieldwork.repository import (
    get_procedure,
    insert_materiality,
    insert_procedure,
    insert_settings,
    list_procedures,
    lock_procedure,
    newest_materiality,
    newest_population,
    newest_results,
    newest_selection,
    newest_settings,
    rule_counts,
    selected_items,
    set_procedure,
    support_requested,
)
from abacus.modules.fieldwork.workflow_types import ProcedureSelectInput
from abacus.modules.fieldwork.workflows import ProcedureSelectWorkflow
from abacus.modules.identity.api import AuthContext, Resource, authorise
from abacus.modules.ledger.api import latest_gl_snapshot
from abacus.modules.sampling.api import DEFAULT_KEYWORDS

WORKFLOWS: dict[type, WorkClass] = {ProcedureSelectWorkflow: "batch"}
register_work_classes(WORKFLOWS)
JOURNAL_ENTRY_TESTING: Final = "journal_entry_testing"
DEFINITION_VERSION: Final = 1
MAX_ITEMS_PAGE: Final = 500


class FieldworkUnavailable(DomainConflict):
    code = "fieldwork_unavailable"


class MaterialityInvalid(DomainInvalid):
    """Amounts are positive, and trivial <= performance <= overall."""

    code = "materiality_invalid"


class MaterialityMissing(DomainConflict):
    """AC-3: a procedure can't select before materiality is set."""

    code = "materiality_missing"


class NoLedger(DomainConflict):
    """No reconciled general ledger for the engagement's entity and year end."""

    code = "no_ledger"


class ProcedureExists(DomainConflict):
    code = "procedure_exists"


class ProcedureBusy(DomainConflict):
    code = "procedure_selecting"


class ParametersInvalid(DomainInvalid):
    code = "parameters_invalid"


# --- Materiality (Q3) ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Materiality:
    overall: Decimal
    performance: Decimal
    trivial: Decimal
    benchmark: str
    set_by: UUID
    set_at: datetime


async def materiality_of(ctx: AuthContext, engagement_id: UUID) -> Materiality | None:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        found = await newest_materiality(session, engagement_id)
    if found is None:
        return None
    return Materiality(
        found.overall,
        found.performance,
        found.trivial,
        found.benchmark,
        found.set_by,
        found.created_at,
    )


async def set_materiality(
    ctx: AuthContext,
    engagement_id: UUID,
    *,
    overall: Decimal,
    performance: Decimal,
    trivial: Decimal,
    benchmark: str,
) -> Materiality:
    """A new version (insert-only); the partner or manager (`materiality.set`)."""
    if not (Decimal(0) < trivial <= performance <= overall) or not benchmark.strip():
        raise MaterialityInvalid(str(engagement_id))
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "materiality.set", ref.resource())
        await insert_materiality(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            overall=overall,
            performance=performance,
            trivial=trivial,
            benchmark=benchmark.strip()[:200],
            set_by=ctx.user_id,
        )
        tx.record("materiality.set", target=Target("engagement", engagement_id))
    found = await materiality_of(ctx, engagement_id)
    if found is None:  # just written in this request
        raise NotFound("materiality")
    return found


# --- Firm defaults (Q6) -------------------------------------------------------------------------


@dataclass(frozen=True)
class Defaults:
    threshold_percent: int = 100
    round_unit: Decimal = Decimal(1000)
    window_days: int = 3
    rare_count: int = 5
    keywords: tuple[str, ...] = DEFAULT_KEYWORDS
    manual_kinds_extra: tuple[str, ...] = ()
    random_count: int = 10

    def as_json(self) -> dict[str, object]:
        return {
            "threshold_percent": self.threshold_percent,
            "round_unit": str(self.round_unit),
            "window_days": self.window_days,
            "rare_count": self.rare_count,
            "keywords": list(self.keywords),
            "manual_kinds_extra": list(self.manual_kinds_extra),
            "random_count": self.random_count,
        }


def defaults_from(raw: dict[str, object] | None) -> Defaults:
    """Validated defaults from stored or submitted JSON (`ParametersInvalid` otherwise)."""
    if not raw:
        return Defaults()
    try:
        found = Defaults(
            threshold_percent=int(cast(int, raw.get("threshold_percent", 100))),
            round_unit=Decimal(str(raw.get("round_unit", "1000"))),
            window_days=int(cast(int, raw.get("window_days", 3))),
            rare_count=int(cast(int, raw.get("rare_count", 5))),
            keywords=tuple(str(k)[:40] for k in cast(list[object], raw.get("keywords", [])))[:50],
            manual_kinds_extra=tuple(
                str(k)[:60] for k in cast(list[object], raw.get("manual_kinds_extra", []))
            )[:20],
            random_count=int(cast(int, raw.get("random_count", 10))),
        )
    except (TypeError, ValueError, InvalidOperation):
        raise ParametersInvalid("defaults") from None
    if not (
        1 <= found.threshold_percent <= 100
        and Decimal(0) <= found.round_unit <= Decimal(1_000_000)
        and 0 <= found.window_days <= 31
        and 0 <= found.rare_count <= 100
        and 0 <= found.random_count <= 200
    ):
        raise ParametersInvalid("defaults")
    return found


async def fieldwork_defaults(ctx: AuthContext) -> Defaults:
    await authorise(ctx, "methodology.read", Resource.firm(ctx.tenant_id))
    async with tenant_session(ctx.tenant) as session:
        return defaults_from(await newest_settings(session))


async def set_fieldwork_defaults(ctx: AuthContext, raw: dict[str, object]) -> Defaults:
    await authorise(ctx, "methodology.manage", Resource.firm(ctx.tenant_id))
    found = defaults_from(raw)
    async with uow(ctx.tenant) as tx:
        await insert_settings(tx.session, ctx.tenant_id, found.as_json(), ctx.user_id)
        tx.record("fieldwork.settings_changed", target=Target("firm", ctx.tenant_id))
    return found


# --- Procedures ---------------------------------------------------------------------------------


@dataclass(frozen=True)
class PopulationView:
    gl_snapshot_id: UUID
    entry_count: int
    line_count: int
    total_debit: Decimal
    total_credit: Decimal
    tied: bool
    failure: str | None


@dataclass(frozen=True)
class SelectionView:
    id: UUID
    item_count: int
    by_rule: dict[str, int]
    seed: int
    created_at: datetime


@dataclass(frozen=True)
class ProcedureView:
    id: UUID
    definition: str
    definition_version: int
    status: str
    failure_code: str | None
    parameters: dict[str, object]
    population: PopulationView | None = None
    selection: SelectionView | None = None
    not_performed: tuple[str, ...] = field(default=("after_year_end", "entered_by"))  # D4


def _summary(p: Procedure) -> ProcedureView:
    return ProcedureView(
        p.id, p.definition, p.definition_version, p.status, p.failure_code, dict(p.parameters)
    )


async def _available(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, _flags.FIELDWORK_PROCEDURES):
        raise FieldworkUnavailable(str(ctx.tenant_id))


async def procedures_of(ctx: AuthContext, engagement_id: UUID) -> list[ProcedureView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        return [_summary(p) for p in await list_procedures(session, ctx, engagement_id)]


async def start_procedure(ctx: AuthContext, engagement_id: UUID) -> ProcedureView:
    """Journal entry testing, once per engagement, with the firm's defaults and a new seed."""
    await _available(ctx)
    async with tenant_session(ctx.tenant) as session:
        defaults = defaults_from(await newest_settings(session))
    parameters: dict[str, object] = {
        **defaults.as_json(),
        "seed": secrets.randbelow(2**31),
        "picks": [],
    }
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "procedure.run", ref.resource())
        procedure_id = await insert_procedure(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            definition=JOURNAL_ENTRY_TESTING,
            definition_version=DEFINITION_VERSION,
            parameters=parameters,
            started_by=ctx.user_id,
        )
        if procedure_id is None:
            raise ProcedureExists(str(engagement_id))
        tx.record(
            "procedure.started",
            target=Target("procedure", procedure_id),
            after=Ref(engagement_id=engagement_id),
        )
    return await procedure_detail(ctx, engagement_id, procedure_id)


async def _owned(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> Procedure:
    async with tenant_session(ctx.tenant) as session:
        found = await get_procedure(session, procedure_id)
    if found is None or found.engagement_id != engagement_id:
        raise NotFound("procedure")
    return found


async def procedure_detail(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID
) -> ProcedureView:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    procedure = await _owned(ctx, engagement_id, procedure_id)
    async with tenant_session(ctx.tenant) as session:
        population = await newest_population(session, procedure_id)
        selection = await newest_selection(session, procedure_id)
        counts = await rule_counts(session, selection.id) if selection is not None else {}
    view = _summary(procedure)
    return ProcedureView(
        view.id,
        view.definition,
        view.definition_version,
        view.status,
        view.failure_code,
        view.parameters,
        PopulationView(
            population.gl_snapshot_id,
            population.entry_count,
            population.line_count,
            population.total_debit,
            population.total_credit,
            population.tied,
            population.failure,
        )
        if population is not None
        else None,
        SelectionView(
            selection.id, selection.item_count, counts, selection.seed, selection.created_at
        )
        if selection is not None
        else None,
    )


async def set_parameters(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, raw: dict[str, object]
) -> ProcedureView:
    """The criteria for the next selection (`procedure.configure`). The seed and picks stay."""
    found = defaults_from(raw)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "procedure.configure", ref.resource())
        procedure = await lock_procedure(tx.session, procedure_id)
        if procedure is None or procedure.engagement_id != engagement_id:
            raise NotFound("procedure")
        if procedure.status == "selecting":
            raise ProcedureBusy(str(procedure_id))
        kept = {k: procedure.parameters.get(k) for k in ("seed", "picks")}
        await set_procedure(tx.session, procedure_id, parameters={**found.as_json(), **kept})
        tx.record("procedure.parameters_changed", target=Target("procedure", procedure_id))
    return await procedure_detail(ctx, engagement_id, procedure_id)


@dataclass(frozen=True)
class Pick:
    key: tuple[str, str, str, str]  # date, type, reference, name (ledger's journal key)
    reason: str


async def add_picks(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, picks: list[Pick]
) -> ProcedureView:
    """People's own picks, each with a reason, applied at the next selection (`procedure.run`)."""
    if any(not p.reason.strip() for p in picks):
        raise ParametersInvalid("picks")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "procedure.run", ref.resource())
        procedure = await lock_procedure(tx.session, procedure_id)
        if procedure is None or procedure.engagement_id != engagement_id:
            raise NotFound("procedure")
        if procedure.status == "selecting":
            raise ProcedureBusy(str(procedure_id))
        existing = cast(list[dict[str, object]], procedure.parameters.get("picks") or [])
        added = [{"key": list(p.key), "reason": p.reason.strip()[:500]} for p in picks]
        await set_procedure(
            tx.session,
            procedure_id,
            parameters={**procedure.parameters, "picks": [*existing, *added][:200]},
        )
        tx.record(
            "procedure.picks_added",
            target=Target("procedure", procedure_id),
            after=Ref(count=len(added)),
        )
    return await procedure_detail(ctx, engagement_id, procedure_id)


async def request_selection(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID
) -> ProcedureView:
    """AC-1, AC-3: start selecting in the background, once materiality and a reconciled ledger
    exist (`procedure.run`)."""
    await _available(ctx)
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.run", ref.resource())
    facts = await check_facts(ctx.tenant, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        materiality = await newest_materiality(session, engagement_id)
    if materiality is None:
        raise MaterialityMissing(str(engagement_id))
    if (
        facts is None
        or await latest_gl_snapshot(ctx.tenant, ref.client_entity_id, facts.fiscal_period_end)
        is None
    ):
        raise NoLedger(str(engagement_id))
    async with uow(ctx.tenant) as tx:
        procedure = await lock_procedure(tx.session, procedure_id)
        if procedure is None or procedure.engagement_id != engagement_id:
            raise NotFound("procedure")
        if procedure.status == "selecting":
            raise ProcedureBusy(str(procedure_id))
        await set_procedure(tx.session, procedure_id, status="selecting", failure_code=None)
        tx.record("procedure.selection_requested", target=Target("procedure", procedure_id))
    event = uuid5(NAMESPACE_URL, f"abacus:select:{procedure_id}:{datetime.now()}")
    await dispatch(
        ProcedureSelectWorkflow,
        ProcedureSelectInput(str(ctx.tenant_id), str(procedure_id), str(ctx.user_id)),
        id=f"procedure_select:{ctx.tenant_id}:{procedure_id}:{event}",
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return await procedure_detail(ctx, engagement_id, procedure_id)


@dataclass(frozen=True)
class ItemView:
    position: int
    posted_on: str
    kind: str
    reference: str
    counterparty: str
    accounts: tuple[str, ...]
    amount: Decimal
    descriptions: tuple[str, ...]
    rules: tuple[str, ...]
    reason: str | None
    id: UUID | None = None
    result: str | None = None  # TASK-078: the newest result
    note: str | None = None
    evidence_version_ids: tuple[UUID, ...] = ()
    support_requested: bool = False


async def items_of(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, *, offset: int, limit: int
) -> list[ItemView]:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    await _owned(ctx, engagement_id, procedure_id)
    async with tenant_session(ctx.tenant) as session:
        selection = await newest_selection(session, procedure_id)
        if selection is None:
            return []
        rows = await selected_items(
            session, selection.id, offset=offset, limit=min(limit, MAX_ITEMS_PAGE)
        )
        results = await newest_results(session, selection.id)
        asked = await support_requested(session, selection.id)
    return [
        ItemView(
            r.position,
            r.posted_on.isoformat(),
            r.kind,
            r.reference,
            r.counterparty,
            tuple(r.accounts),
            r.amount,
            tuple(r.descriptions),
            tuple(r.rules),
            r.reason,
            r.id,
            results[r.id].result if r.id in results else None,
            results[r.id].note if r.id in results else None,
            tuple(results[r.id].evidence_version_ids or []) if r.id in results else (),
            r.id in asked,
        )
        for r in rows
    ]
