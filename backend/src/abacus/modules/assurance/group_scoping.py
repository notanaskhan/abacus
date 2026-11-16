"""AUD-34 group scoping (A-09-T23 rest; SPEC-658 F5, AC-5.1 to AC-5.3; DEC-5330; amber).

- **Group materiality** is the EP's reserved decision (`group_materiality`, C1 decision card,
  rationale and fresh MFA through P-04's decide). Its options are code's: the firm's K-02
  `materiality_ranges` policy (A-04's `firm_policy`) over the consolidated Level 1 benchmark
  (total assets, or net income when the policy names an earnings benchmark), PM at 75% and the
  policy's clearly-trivial rate (`compute.group_scoping`). The decided option is recomputed from
  the same inputs on read; nothing here stores a figure the card did not.
- **Components** (`components`): planned work, scope areas, who performs it and the component PM;
  a person's edit with `If-Match`; a PM at or above group PM, or any PM on an Analytical-only
  component, is 422 `component_pm_invalid`.
- **Coverage** by code (`compute.group_scoping.coverage`): each entity's total assets before
  eliminations from the consolidated Level 1, split by planned work.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.assurance.compute import group_scoping as calc
from abacus.modules.assurance.compute import materiality as engine
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.ledger import api as ledger
from abacus.modules.review.api import CardSubject, ComputedCard

KIND: Final = "group_materiality"
QUESTION: Final = "group_materiality"
Planned = Literal["full_scope", "specific_procedures", "analytical_only"]


class ComponentPmInvalid(DomainInvalid):
    code = "component_pm_invalid"


class ComponentStale(DomainConflict):
    code = "version_stale"


class NoConsolidation(DomainConflict):
    code = "consolidation_missing"


@dataclass(frozen=True)
class ComponentRow:
    id: UUID
    consolidation_entity_id: UUID
    client_entity_id: UUID
    entity_name: str
    planned_work: Planned
    scope_areas: tuple[str, ...]
    performed_by: Literal["group_team", "component_auditor"]
    component_pm: Decimal | None
    row_version: int


@dataclass(frozen=True)
class Scoping:
    card_id: UUID | None
    decided: calc.GroupThresholds | None
    decided_by: UUID | None
    decided_at: datetime | None
    options: tuple[tuple[str, str, Decimal, calc.GroupThresholds], ...]  # key, benchmark, base
    components: tuple[ComponentRow, ...]
    component_pm_total: Decimal
    coverage: calc.Coverage | None
    full_scope: Decimal
    specific: Decimal
    total_assets: Decimal


_COMPONENTS: Final = text(
    "SELECT id, consolidation_entity_id, planned_work, scope_areas, performed_by, component_pm, "
    "row_version FROM components WHERE work_item_id = :w ORDER BY created_at, id"
)
_ONE: Final = text(
    "SELECT id, work_item_id, engagement_id, row_version FROM components WHERE id = :c"
)
_EDIT: Final = text(
    "UPDATE components SET planned_work = :p, scope_areas = :a, performed_by = :b, "
    "component_pm = :pm, row_version = row_version + 1 WHERE id = :c AND row_version = :v "
    "RETURNING row_version"
)


async def _consolidation(tenant: TenantContext, work_item_id: UUID) -> ledger.ConsolidationFacts:
    for consolidation_id in await ledger.consolidations_of(tenant, work_item_id):
        facts = await ledger.consolidation_facts(tenant, consolidation_id)
        if facts.status == "finalized":
            return facts
    raise NoConsolidation(facts={"work_item_id": str(work_item_id)})


async def _level_one(
    tenant: TenantContext, facts: ledger.ConsolidationFacts
) -> ledger.ConsolidationLevel | None:
    from abacus.modules.assurance.group_tb import levels_for

    found, _, _ = await levels_for(tenant, facts)
    return next((lv for lv in found if lv.level == 1), None)


def _entity_assets(level: ledger.ConsolidationLevel) -> dict[str, Decimal]:
    return {
        column: sum((r.amount(column) for r in level.rows if r.section == "assets"), Decimal(0))
        for column in level.columns
        if column not in (ledger.ELIMINATIONS_COLUMN, ledger.CONSOLIDATED_COLUMN)
    }


async def _options(
    tenant: TenantContext, work_item_id: UUID, level: ledger.ConsolidationLevel, as_of: object
) -> tuple[tuple[str, str, Decimal, calc.GroupThresholds], ...]:
    from abacus.modules.assurance.materiality import firm_policy

    found = await firm_policy(tenant, work_item_id, as_of)  # type: ignore[arg-type] -- a date
    earnings = any(w in found.benchmark_key for w in ("income", "earnings", "profit"))
    base = abs(level.net_income) if earnings else level.total_assets
    label = found.benchmark_label
    out: list[tuple[str, str, Decimal, calc.GroupThresholds]] = []
    for option in engine.options(
        basis="unadjusted",
        benchmark_key=found.benchmark_key,
        benchmark_amount=base,
        pm_pct=calc.PM_PCT,
        ct_pct=found.policy.ct_pct,
        policy=found.policy,
    ):
        if option.thresholds is None:
            continue  # "custom" is A-04's own card's
        out.append((option.key, label, base, calc.thresholds(option.thresholds.overall)))
    return tuple(out)


async def card_options(tenant: TenantContext, subject: CardSubject) -> ComputedCard:
    """The `group_materiality` kind's provider: code's options over the consolidated Level 1."""
    from abacus.modules.review.api import CardContext, CardOption

    if subject.work_item_id is None:
        raise NoConsolidation(facts={"engagement_id": str(subject.engagement_id)})
    work_item_id = subject.work_item_id
    facts = await _consolidation(tenant, work_item_id)
    level = await _level_one(tenant, facts)
    if level is None:
        raise NoConsolidation(facts={"work_item_id": str(work_item_id)})
    options = await _options(tenant, work_item_id, level, facts.year_end)
    return ComputedCard(
        options=tuple(
            CardOption(
                key=key,
                label=f"{t.materiality:,.0f} · PM {t.pm:,.0f} · CT {t.ct:,.0f}",
                figures={"overall": str(t.materiality), "pm": str(t.pm), "ct": str(t.ct)},
            )
            for key, _, _, t in options
        ),
        context=tuple(
            CardContext(key="benchmark", label="Benchmark", value=f"{label} {base:,.0f}")
            for _, label, base, _ in options[:1]
        ),
    )


def register() -> None:
    """At import (assurance/api.py): the EP's reserved card kind."""
    from abacus.modules.review.api import DecisionKind, register_decision_kind

    register_decision_kind(
        DecisionKind(
            code=KIND,
            reserved_role="engagement_partner",
            options=card_options,
            questions={QUESTION: "Group materiality"},
        )
    )


async def _names(tenant: TenantContext, entity_ids: list[UUID]) -> dict[UUID, str]:
    from abacus.modules.organisations.api import client_names

    async with tenant_session(tenant) as session:
        found = await client_names(session, entity_ids)
    return {k: v.client_entity_name for k, v in found.items()}


async def scoping(ctx: AuthContext, work_item_id: UUID, engagement_id: UUID) -> Scoping:
    """AUD-34 for a person allowed `group_scoping.read` (the route authorised it)."""
    from abacus.modules.review.api import awaiting_cards, decided_cards

    tenant = ctx.tenant
    facts = await _consolidation(tenant, work_item_id)
    by_entity = {e.id: e.client_entity_id for e in facts.entities}
    names = await _names(tenant, list(by_entity.values()))
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_COMPONENTS, {"w": work_item_id})).mappings().all()
    components = tuple(
        ComponentRow(
            id=r["id"],
            consolidation_entity_id=r["consolidation_entity_id"],
            client_entity_id=by_entity.get(cast(UUID, r["consolidation_entity_id"]))
            or cast(UUID, r["consolidation_entity_id"]),
            entity_name=names.get(
                by_entity.get(cast(UUID, r["consolidation_entity_id"])) or cast(UUID, r["id"]), ""
            ),
            planned_work=r["planned_work"],
            scope_areas=tuple(r["scope_areas"] or ()),
            performed_by=r["performed_by"],
            component_pm=r["component_pm"],
            row_version=int(r["row_version"]),
        )
        for r in rows
    )
    level = await _level_one(tenant, facts)
    options = () if level is None else await _options(tenant, work_item_id, level, facts.year_end)
    decided = next(
        (
            d
            for d in await decided_cards(tenant, engagement_id)
            if d.kind == KIND and d.question_key == QUESTION
        ),
        None,
    )
    chosen = None
    if decided is not None:
        chosen = next((t for key, _, _, t in options if key == decided.option_key), None)
    waiting = next(iter(await awaiting_cards(tenant, work_item_id, [KIND])), None)
    assets = {} if level is None else _entity_assets(level)
    planned: dict[str, calc.Planned] = {
        str(c.consolidation_entity_id): c.planned_work for c in components
    }
    total = Decimal(0) if level is None else level.total_assets
    cover = (
        None if level is None else calc.coverage(assets, planned, sum(assets.values(), Decimal(0)))
    )
    full = sum((v for k, v in assets.items() if planned.get(k) == "full_scope"), Decimal(0))
    specific = sum(
        (v for k, v in assets.items() if planned.get(k) == "specific_procedures"), Decimal(0)
    )
    return Scoping(
        card_id=decided.card_id if decided is not None else (waiting.card_id if waiting else None),
        decided=chosen,
        decided_by=decided.decided_by if decided is not None else None,
        decided_at=decided.decided_at if decided is not None else None,
        options=options,
        components=components,
        component_pm_total=sum((c.component_pm or Decimal(0) for c in components), Decimal(0)),
        coverage=cover,
        full_scope=full,
        specific=specific,
        total_assets=total,
    )


async def raise_card(ctx: AuthContext, work_item_id: UUID, engagement_id: UUID) -> UUID:
    from abacus.modules.review.api import raise_decision_card

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("group_materiality.propose", "role")
    return await raise_decision_card(
        ctx,
        engagement_id=engagement_id,
        kind=KIND,
        question_key=QUESTION,
        work_item_id=work_item_id,
        raised_under="group_materiality.propose",
    )


async def edit_component(
    ctx: AuthContext,
    component_id: UUID,
    *,
    planned_work: Planned,
    scope_areas: list[str],
    performed_by: str,
    component_pm: Decimal | None,
    seen_version: int,
) -> ComponentRow:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden("component.edit", "role")
    from abacus.modules.engagements.api import engagement_resource_of
    from abacus.modules.identity.api import authorise

    async with tenant_session(ctx.tenant) as session:
        head = (await session.execute(_ONE, {"c": component_id})).mappings().first()
    if head is None:
        raise NotFound("component")
    await authorise(
        ctx, "component.edit", await engagement_resource_of(ctx.tenant, head["engagement_id"])
    )
    if component_pm is not None:
        if planned_work == "analytical_only":
            raise ComponentPmInvalid(facts={"field": "component_pm"})
        found = await scoping(ctx, head["work_item_id"], head["engagement_id"])
        if found.decided is None:
            raise ComponentPmInvalid(facts={"field": "group_materiality"})
        try:
            calc.validate_component_pm(component_pm, found.decided.pm)
        except calc.ComponentPmTooHigh:
            raise ComponentPmInvalid(facts={"field": "component_pm"}) from None
    async with uow(ctx.tenant) as tx:
        bumped = await tx.session.scalar(
            _EDIT,
            {
                "p": planned_work,
                "a": list(scope_areas),
                "b": performed_by,
                "pm": component_pm,
                "c": component_id,
                "v": seen_version,
            },
        )
        if bumped is None:
            raise ComponentStale(facts={"component_id": str(component_id)})
        tx.record(
            "component.edited", target=Target("component", component_id), after=Ref(version=bumped)
        )
    after = await scoping(ctx, head["work_item_id"], head["engagement_id"])
    return next(c for c in after.components if c.id == component_id)


async def workbook(ctx: AuthContext, work_item_id: UUID, engagement_id: UUID) -> bytes:
    from abacus.kernel.safe_xlsx import Cell, Sheet
    from abacus.kernel.safe_xlsx import workbook as render

    found = await scoping(ctx, work_item_id, engagement_id)
    rows: list[list[Cell]] = [
        ["Component", "Planned work", "Performed by", "Component PM", "Scope areas"]
    ]
    for c in found.components:
        rows.append(
            [
                c.entity_name,
                c.planned_work,
                c.performed_by,
                c.component_pm,
                ", ".join(c.scope_areas),
            ]
        )
    rows.append(["Total component PM", "", "", found.component_pm_total, ""])
    return render([Sheet("Group scoping", rows)])
