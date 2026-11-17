"""Audit analytics (A-08-T21; A-08 §3 F5; SPEC-657 AC-5.1 to AC-5.6; AUD-13 a to e; DEC-5400;
amber).

- **Run** (`analytics.run`, a person): a new analytics-set version over a trial balance layer
  (Unadjusted for preliminary and substantive, the adjusted Final layer for final) against
  prior-year figures, thresholded at the firm's percentage **and** the materiality version's PM
  (provisional until the partner decides). `FluxAnalyticsWorkflow` computes it with the shared
  dual-threshold engine (`workpapers.compute.flux`): the lines are code's, insert-only; the set
  becomes Current and the one before it reads Superseded. A recompute never edits.
- **`materiality.decided`**: each Current preliminary set of that work item gets a new version
  at the decided PM; an explanation carries forward (with its acceptance) only where the line's
  over/within result did not change, so a line that changed status goes back to Unexplained.
- **Explain** (`analytics.explain`): text and >= 1 citation that code verified and that is still
  valid on the engagement, else 422 `explanation_uncited`. An adopted agent suggestion names its
  suggestion; the agent itself never explains (it proposes through `suggestion.create`).
- **Accept** (`analytics.accept`, SHL-10): a manager or the partner, never the explanation's
  author (`not_preparer_of_target`); `seen_hash` must be the set's review hash (409
  `content_changed`).
- **Client questions** (`client_question.send`, DV-4): one T-02 questionnaire to the client
  contact, one question per card, worded from a firm template a person edited, then sent; the
  answer comes back as a `client_answer` explanation ("Client answer Sep 16 · Luis Ferrante").
- **Export**: a deterministic workbook (formula-injection guard on every text cell).
- **Prior-year figures**: an import (each figure cited) or the prior engagement's figures as the
  trial balance's prior period carries them; numbered imports, insert-only.

Money is `Decimal`; no model computes anything here (ADR-050).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Annotated, ClassVar, Final, Literal, cast
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy, WorkflowIDConflictPolicy, WorkflowIDReusePolicy

with workflow.unsafe.imports_passed_through():
    from sqlalchemy import text

    from abacus.kernel.classification import classified
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
    from abacus.kernel.safe_xlsx import Cell, Sheet, workbook
    from abacus.kernel.uow import DomainEvent, Ref, Target, UnitOfWork, uow
    from abacus.kernel.uow.relay import OutboxEvent
    from abacus.modules.identity.api import (
        AuthContext,
        Forbidden,
        Resource,
        TargetFacts,
        allowed_actions,
        authorise,
        engagement_partners,
        names_of,
    )
    from abacus.modules.workpapers.api import (
        FLUX_ENGINE_VERSION,
        FluxLine,
        FluxSet,
        Thresholds,
        evaluate_flux,
    )

TARGET: Final = "analytics_set"
SYSTEM_ACTOR: Final = "analytics"
# AU-C 520's percentage leg: the firm's 10% until a firm threshold policy is configured
# (A-08-T22's SSARS variance policy is the first such policy; DEC-5400).
DEFAULT_PCT: Final = Decimal("10")
READ: Final = "analytics.read"
ACTIONS: Final = (
    "analytics.explain",
    "analytics.accept",
    "analytics.configure",
    "client_question.send",
    "analytics.export",
)
_I = classified("internal")

Stage = Literal["preliminary", "substantive", "final", "review"]
Kind = Literal["audit_flux", "ssars_review"]
LineStatus = Literal["within", "unexplained", "explained", "accepted"]


# --- events --------------------------------------------------------------------------------------


class AnalyticsComputed(DomainEvent):
    """A set version is Current (AUD-13's tallies land; the manager's gate may open)."""

    event_type: ClassVar[str] = "analytics.computed"

    analytics_set_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    work_item_id: Annotated[UUID, _I]
    version_no: Annotated[int, _I]


class AnalyticsExplanationRecorded(DomainEvent):
    """An explanation counts on a line: the manager's acceptance gate may open."""

    event_type: ClassVar[str] = "analytics.explanation_recorded"

    analytics_set_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    explanation_id: Annotated[UUID, _I]


class AnalyticsExplanationAccepted(DomainEvent):
    event_type: ClassVar[str] = "analytics.explanation_accepted"

    analytics_set_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    accepted: Annotated[int, _I]


class ClientQuestionSent(DomainEvent):
    event_type: ClassVar[str] = "client_question.sent"

    analytics_set_id: Annotated[UUID, _I]
    engagement_id: Annotated[UUID, _I]
    questionnaire_id: Annotated[UUID, _I]


# --- errors --------------------------------------------------------------------------------------


class ExplanationUncited(DomainInvalid):
    """AC-5.3: an explanation without a verified, still-valid citation."""

    code = "explanation_uncited"


class MaterialityRequired(DomainConflict):
    """The amount leg comes from a materiality version; none is recorded yet."""

    code = "materiality_required"


class AnalyticsComputing(DomainConflict):
    code = "analytics_computing"


class SetNotCurrent(DomainConflict):
    """Explanations, acceptance and questions act on the Current version only."""

    code = "analytics_set_not_current"


class LineNotOver(DomainInvalid):
    """Only an evaluated line over the threshold takes an explanation or a question."""

    code = "analytics_line_not_over"


class LayerStageMismatch(DomainInvalid):
    """Final analytics read the adjusted layer; preliminary and substantive the unadjusted."""

    code = "analytics_layer_stage_mismatch"


class ContentChanged(DomainConflict):
    code = "content_changed"


class QuestionCardsMismatch(DomainInvalid):
    """One card per line asked about, in the same order."""

    code = "question_cards_mismatch"


class PriorYearFiguresMissing(DomainConflict):
    """An import run with no imported prior-year figures."""

    code = "prior_year_figures_missing"


# --- views ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ThresholdFacts:
    pct: Decimal
    amount: Decimal
    materiality_version_id: UUID | None
    overall: Decimal | None
    provisional: bool
    decider_name: str | None = None


@dataclass(frozen=True)
class ExplanationView:
    id: UUID
    text: str
    citation_ids: tuple[UUID, ...]
    source: str
    suggestion_id: UUID | None
    authored_by: UUID | None
    authored_by_name: str
    client_answered_on: date | None
    accepted_by: UUID | None
    accepted_by_initials: str | None


@dataclass(frozen=True)
class ExpectationView:
    low_pct: Decimal | None
    high_pct: Decimal | None
    low: Decimal | None
    high: Decimal | None
    basis: str


@dataclass(frozen=True)
class LineView:
    position: int
    fs_line_key: str
    caption: str
    group_key: str
    cy: Decimal
    py: Decimal
    change: Decimal
    change_pct: Decimal | None
    evaluated: bool
    over: bool
    derived: bool
    status: LineStatus | None
    explanation: ExplanationView | None
    expectation: ExpectationView | None
    sources: tuple[str, ...]
    cell: str


@dataclass(frozen=True)
class Tallies:
    lines: int
    over_threshold: int
    explained: int
    unexplained: int
    tb_balanced: bool


@dataclass(frozen=True)
class SetView:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    kind: Kind
    stage: Stage
    version_no: int
    status: str
    basis_label: str
    threshold: ThresholdFacts
    tallies: Tallies
    lines: tuple[LineView, ...]
    engine_version: str
    inputs_hash: str
    review_hash: str
    allowed_actions: tuple[str, ...]
    failure_code: str | None = None


@dataclass(frozen=True)
class Provenance:
    cell: str
    formula: str
    sources: tuple[str, ...]


# --- the pure parts ------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceLine:
    """One FS line of the statements as the run reads it."""

    key: str
    caption: str
    group_key: str
    group_label: str
    cy: Decimal
    py: Decimal
    sources: tuple[str, ...]


@dataclass(frozen=True)
class ComputedLine:
    position: int
    key: str
    caption: str
    group_key: str
    cy: Decimal
    py: Decimal
    change: Decimal
    change_pct: Decimal | None
    evaluated: bool
    over: bool
    derived: bool
    sources: tuple[str, ...]
    cell: str


def cell_of(position: int) -> str:
    """The workbook cell a line's current figure sits in (row 1 is the header)."""
    return f"D{position + 1}"


def compute_lines(
    source: Sequence[SourceLine], thresholds: Thresholds
) -> tuple[tuple[ComputedLine, ...], FluxSet]:
    """Each group's FS lines, then the group's subtotal when it has more than one line (derived,
    never evaluated); the engine decides change, change % and over/within."""
    lines: list[FluxLine] = []
    groups: dict[str, list[SourceLine]] = {}
    for line in source:
        groups.setdefault(line.group_key, []).append(line)
    meta: list[tuple[str, str, tuple[str, ...]]] = []  # (key, group_key, sources)
    for group_key, members in groups.items():
        for m in members:
            lines.append(FluxLine(m.key, m.caption, m.cy, m.py))
            meta.append((m.key, group_key, m.sources))
        if len(members) > 1:
            total = f"{group_key}:total"
            lines.append(
                FluxLine(
                    total,
                    members[0].group_label,
                    sum((m.cy for m in members), Decimal(0)),
                    sum((m.py for m in members), Decimal(0)),
                    derived_from=tuple(m.key for m in members),
                )
            )
            meta.append((total, group_key, ()))
    result = evaluate_flux(lines, thresholds)
    computed = tuple(
        ComputedLine(
            position=n,
            key=row.key,
            caption=row.label,
            group_key=group_key,
            cy=row.current,
            py=row.prior,
            change=row.change,
            change_pct=row.change_pct,
            evaluated=not row.derived,
            over=row.result == "over",
            derived=row.derived,
            sources=sources,
            cell=cell_of(n),
        )
        for n, (row, (_, group_key, sources)) in enumerate(
            zip(result.rows, meta, strict=True), start=1
        )
    )
    return computed, result


def content_hash(lines: Sequence[ComputedLine]) -> str:
    body = json.dumps(
        [
            [x.position, x.key, str(x.cy), str(x.py), str(x.change), x.over, x.derived]
            for x in lines
        ],
        sort_keys=True,
    )
    return hashlib.sha256(body.encode()).hexdigest()


def line_status(
    line: LineView | ComputedLine, explanation: ExplanationView | None
) -> LineStatus | None:
    if line.derived:
        return None
    if not line.over:
        return "within"
    if explanation is None:
        return "unexplained"
    return "accepted" if explanation.accepted_by is not None else "explained"


def review_hash(set_id: UUID, version_no: int, lines: Sequence[LineView]) -> str:
    """What SHL-10 shows the acceptor: each line's status and its explanation."""
    body = json.dumps(
        {
            "set": str(set_id),
            "v": version_no,
            "lines": [
                [x.position, x.status, str(x.explanation.id) if x.explanation else None]
                for x in lines
            ],
        },
        sort_keys=True,
    )
    return hashlib.sha256(body.encode()).hexdigest()


def basis_label(kind: Kind, layer: str, period_end: date) -> str:
    year = period_end.year
    if kind == "ssars_review":
        return f"FY{year} vs FY{year - 1}"
    lead = "Adjusted" if layer == "adjusted" else "Unadjusted"
    return f"{lead} FY{year} vs audited FY{year - 1}"


def initials(name: str) -> str:
    return "".join(part[0] for part in name.split() if part)[:3].upper()


# --- SQL -----------------------------------------------------------------------------------------

_SET: Final = text(
    "SELECT id, engagement_id, work_item_id, kind, stage, version_no, cy_trial_balance_id, "
    "cy_layer, py_source, threshold_pct, threshold_amount, materiality_version_id, provisional, "
    "engine_version, basis_label, run_parameters, inputs_hash, content_hash, tb_balanced, "
    "status, failure_code, created_by FROM analytics_sets WHERE id = :id"
)
_LIVE: Final = text(
    "SELECT id, status FROM analytics_sets WHERE work_item_id = :w AND kind = :k AND stage = :s "
    "AND status IN ('computing', 'current')"
)
_NEXT_VERSION: Final = text(
    "SELECT coalesce(max(version_no), 0) + 1 FROM analytics_sets "
    "WHERE work_item_id = :w AND kind = :k AND stage = :s"
)
_INSERT_SET: Final = text(
    "INSERT INTO analytics_sets (tenant_id, engagement_id, work_item_id, kind, stage, version_no, "
    "cy_trial_balance_id, cy_layer, py_source, threshold_pct, threshold_amount, "
    "materiality_version_id, threshold_policy_version_id, provisional, engine_version, "
    "basis_label, created_by, run_parameters) VALUES (:t, :e, :w, :k, :s, :v, :tb, :layer, :py, "
    ":pct, :amount, :mv, :policy, :prov, :engine, :label, :by, CAST(:params AS jsonb)) "
    "RETURNING id"
)
_INSERT_LINE: Final = text(
    "INSERT INTO analytics_lines (tenant_id, set_id, position, fs_line_key, caption, group_key, "
    "cy, py, change, change_pct, evaluated, over, derived, status, sources, cell) VALUES (:t, "
    ":set, :pos, :key, :caption, :group, :cy, :py, :change, :pct, :evaluated, :over, :derived, "
    ":status, :sources, :cell)"
)
_SUPERSEDE: Final = text(
    "UPDATE analytics_sets SET status = 'superseded', superseded_by = :new "
    "WHERE work_item_id = :w "
    "AND kind = :k AND stage = :s AND status IN ('current', 'out_of_date') AND id <> :new"
)
_COMPLETE: Final = text(
    "UPDATE analytics_sets SET status = 'current', inputs_hash = :ih, content_hash = :ch, "
    "computed_at = clock_timestamp(), tb_balanced = :bal WHERE id = :id AND status = 'computing' "
    "RETURNING id"
)
_FAIL: Final = text(
    "UPDATE analytics_sets SET status = 'out_of_date', failure_code = :code, "
    "computed_at = clock_timestamp() WHERE id = :id AND status = 'computing'"
)
_LINES: Final = text(
    "SELECT position, fs_line_key, caption, group_key, cy, py, change, change_pct, evaluated, "
    "over, derived, sources, cell FROM analytics_lines WHERE set_id = :set ORDER BY position"
)
_EXPLANATIONS: Final = text(
    "SELECT DISTINCT ON (line_position) id, line_position, text, citation_ids, source, "
    "suggestion_id, question_id, authored_by, answered_by_contact_id, accepted_by, accepted_at, "
    "created_at "
    "FROM analytics_explanations WHERE set_id = :set "
    "ORDER BY line_position, created_at DESC, id DESC"
)
_EXPECTATIONS: Final = text(
    "SELECT DISTINCT ON (line_position) line_position, low, high, pct_low, pct_high, basis "
    "FROM analytics_expectations WHERE set_id = :set "
    "ORDER BY line_position, set_at DESC, id DESC"
)
_INSERT_EXPLANATION: Final = text(
    "INSERT INTO analytics_explanations (tenant_id, set_id, line_position, text, citation_ids, "
    "source, suggestion_id, question_id, answered_by_contact_id, authored_by, carried_from_id, "
    "accepted_by, accepted_at) VALUES (:t, :set, :pos, :text, :cites, :source, :sug, :q, "
    ":contact, :by, :carried, :accepted_by, :accepted_at) RETURNING id"
)
_ACCEPT: Final = text(
    "UPDATE analytics_explanations SET accepted_by = :by, accepted_at = clock_timestamp() "
    "WHERE id = :id AND accepted_by IS NULL RETURNING id"
)
_EXPLANATION_TIMES: Final = text(
    "SELECT id, accepted_at, created_at FROM analytics_explanations WHERE id = ANY(:ids)"
)
_CURRENT_PRELIMINARY: Final = text(
    "SELECT id FROM analytics_sets WHERE work_item_id = :w AND kind = 'audit_flux' "
    "AND stage = 'preliminary' AND status = 'current'"
)
_BY_EVENT: Final = text(
    "SELECT id FROM analytics_sets WHERE work_item_id = :w AND run_parameters ->> 'event_id' = :ev"
)
_PY_LATEST: Final = text(
    "SELECT fs_line_key, amount FROM prior_year_figures WHERE work_item_id = :w AND import_no = "
    "(SELECT max(import_no) FROM prior_year_figures WHERE work_item_id = :w)"
)
_PY_NEXT: Final = text(
    "SELECT coalesce(max(import_no), 0) + 1 FROM prior_year_figures WHERE work_item_id = :w"
)
_PY_INSERT: Final = text(
    "INSERT INTO prior_year_figures (tenant_id, engagement_id, work_item_id, import_no, source, "
    "fs_line_key, amount, citation_id, imported_by) VALUES (:t, :e, :w, :n, :source, :key, "
    ":amount, :cite, :by)"
)
_INSERT_QUESTION: Final = text(
    "INSERT INTO analytics_questions (tenant_id, set_id, line_position, questionnaire_id, "
    "question_id, template_key, sent_by) VALUES (:t, :set, :pos, :qn, :q, :tpl, :by)"
)
_QUESTION_OF: Final = text(
    "SELECT q.set_id, q.line_position, s.engagement_id, s.status FROM analytics_questions q "
    "JOIN analytics_sets s ON s.id = q.set_id WHERE q.question_id = :q"
)


def _row(found: object) -> dict[str, object]:
    return dict(cast("Mapping[str, object]", found))


async def _set_row(tenant: TenantContext, set_id: UUID) -> dict[str, object]:
    async with tenant_session(tenant) as session:
        found = (await session.execute(_SET, {"id": set_id})).mappings().first()
    if found is None:
        raise NotFound(TARGET)
    return _row(found)


async def _resource(
    ctx: AuthContext, engagement_id: UUID, preparers: frozenset[UUID] | None = None
) -> Resource:
    from dataclasses import replace

    from abacus.modules.engagements.api import get_ref

    resource = (await get_ref(ctx, engagement_id)).resource()
    if preparers is None:
        return resource
    return replace(resource, target=TargetFacts(preparer_user_ids=preparers))


def _person(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


# --- threshold -----------------------------------------------------------------------------------


async def threshold_for(tenant: TenantContext, work_item_id: UUID) -> ThresholdFacts:
    """10% **and** PM from the materiality version in force, else the current (provisional)."""
    from abacus.modules.assurance.materiality import current_of, in_force, versions_of

    versions = await versions_of(tenant, work_item_id)
    decided = in_force(versions)
    chosen = decided or current_of(versions)
    if chosen is None:
        raise MaterialityRequired(facts={"work_item": str(work_item_id)})
    return ThresholdFacts(DEFAULT_PCT, chosen.pm, chosen.id, chosen.overall, decided is None)


async def _decider(ctx: AuthContext, engagement_id: UUID) -> str | None:
    """The engagement partner who decides the set (identity names the role, ADR-020)."""
    partners = await engagement_partners(ctx.tenant.tenant_id, engagement_id)
    if not partners:
        return None
    return (await names_of(partners[:1])).get(partners[0])


# --- run -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunInput:
    tenant_id: str
    analytics_set_id: str


async def _start(
    tenant: TenantContext,
    *,
    engagement_id: UUID,
    work_item_id: UUID,
    kind: Kind,
    stage: Stage,
    trial_balance_id: UUID,
    layer: str,
    py_source: str,
    threshold: ThresholdFacts,
    created_by: UUID,
    params: dict[str, object],
    policy_version_id: UUID | None = None,
) -> tuple[UUID, int]:
    from abacus.modules.ledger import api as ledger

    tb = await ledger.trial_balance_view(tenant, engagement_id, trial_balance_id)
    label = basis_label(kind, layer, tb.summary.period_end)
    async with uow(tenant) as tx:
        live = (await tx.session.execute(_LIVE, {"w": work_item_id, "k": kind, "s": stage})).all()
        if any(r.status == "computing" for r in live):
            raise AnalyticsComputing(facts={"work_item": str(work_item_id)})
        version_no = int(
            cast(
                int,
                await tx.session.scalar(_NEXT_VERSION, {"w": work_item_id, "k": kind, "s": stage}),
            )
        )
        set_id = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_SET,
                {
                    "t": tenant.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "k": kind,
                    "s": stage,
                    "v": version_no,
                    "tb": trial_balance_id,
                    "layer": layer,
                    "py": py_source,
                    "pct": threshold.pct,
                    "amount": threshold.amount,
                    "mv": threshold.materiality_version_id,
                    "policy": policy_version_id,
                    "prov": threshold.provisional,
                    "engine": FLUX_ENGINE_VERSION,
                    "label": label,
                    "by": created_by,
                    "params": json.dumps(params, sort_keys=True),
                },
            ),
        )
        tx.record(
            "analytics.run_requested",
            target=Target(TARGET, set_id),
            after=Ref(version=version_no),
        )
    await _dispatch(tenant, set_id, version_no)
    return set_id, version_no


async def _dispatch(tenant: TenantContext, set_id: UUID, version_no: int) -> None:
    from abacus.kernel.dispatch import dispatch

    await dispatch(
        FluxAnalyticsWorkflow,
        RunInput(str(tenant.tenant_id), str(set_id)),
        id=f"flux:{tenant.tenant_id}:{set_id}:{version_no}",
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )


async def run(
    ctx: AuthContext,
    work_item_id: UUID,
    *,
    kind: Kind,
    stage: Stage,
    trial_balance_id: UUID,
    layer: str,
    py_source: str,
) -> tuple[UUID, int]:
    """`POST …/analytics-sets` (the route authorised `analytics.run`): 202, then the workflow."""
    from abacus.modules.engagements.api import work_item_engagement

    _person(ctx, "analytics.run")
    if (stage == "final") != (layer == "adjusted"):
        raise LayerStageMismatch(facts={"stage": stage, "layer": layer})
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    if kind == "ssars_review":
        from abacus.modules.assurance.ssars import review_threshold

        found, policy = await review_threshold(ctx.tenant, work_item_id)
        threshold = cast(ThresholdFacts, found)
    else:
        threshold, policy = await threshold_for(ctx.tenant, work_item_id), None
    return await _start(
        ctx.tenant,
        engagement_id=engagement_id,
        work_item_id=work_item_id,
        kind=kind,
        stage=stage,
        trial_balance_id=trial_balance_id,
        layer=layer,
        py_source=py_source,
        threshold=threshold,
        created_by=ctx.user_id,
        params={},
        policy_version_id=policy,
    )


async def _source_lines(
    tenant: TenantContext, row: Mapping[str, object]
) -> tuple[list[SourceLine], bool] | None:
    """The run's FS lines: CY from the layer, PY from the import or the TB's prior period."""
    from abacus.modules.ledger import api as ledger

    engagement_id = cast(UUID, row["engagement_id"])
    view = await ledger.mapping_view(tenant, engagement_id, cast(UUID, row["cy_trial_balance_id"]))
    if view is None:
        return None
    layer = "final" if row["cy_layer"] == "adjusted" else "unadjusted"
    statements = ledger.build_statements(view.groupings, view.accounts, layer)
    codes: dict[UUID, list[str]] = {}
    for account in view.accounts:
        if account.fs_line_id is not None:
            codes.setdefault(account.fs_line_id, []).append(account.account_code)
    ids = {line.key: line.id for g in view.groupings for line in g.lines}
    imported: dict[str, Decimal] = {}
    if row["py_source"] == "import":
        async with tenant_session(tenant) as session:
            imported = {
                str(r.fs_line_key): Decimal(r.amount)
                for r in await session.execute(_PY_LATEST, {"w": row["work_item_id"]})
            }
        if not imported:
            raise PriorYearFiguresMissing(facts={"work_item": str(row["work_item_id"])})
    out: list[SourceLine] = []
    for group in statements.groups:
        for line in group.lines:
            prior = (
                imported.get(line.key, Decimal(0))
                if row["py_source"] == "import"
                else (line.py if line.py is not None else Decimal(0))
            )
            fs_id = ids.get(line.key)
            out.append(
                SourceLine(
                    key=line.key,
                    caption=line.label,
                    group_key=group.key,
                    group_label=group.label,
                    cy=line.cy,
                    py=prior,
                    sources=tuple(sorted(codes.get(fs_id, []))) if fs_id else (),
                )
            )
    return out, statements.balanced


async def compute_set(tenant: TenantContext, set_id: UUID) -> str:
    """The workflow's one activity: lines, stamp, Current; the previous version Superseded."""
    row = await _set_row(tenant, set_id)
    if row["status"] != "computing":
        return str(row["status"])
    try:
        found = await _source_lines(tenant, row)
    except PriorYearFiguresMissing:
        found = None
        failure = "prior_year_figures_missing"
    else:
        failure = "mapping_missing"
    if found is None:
        async with uow(tenant) as tx:
            await tx.session.execute(_FAIL, {"id": set_id, "code": failure})
            tx.record("analytics.compute_failed", target=Target(TARGET, set_id))
        return "out_of_date"
    source, balanced = found
    thresholds = Thresholds(
        Decimal(str(row["threshold_pct"])), Decimal(str(row["threshold_amount"]))
    )
    lines, result = compute_lines(source, thresholds)
    params = row["run_parameters"]
    params = (
        json.loads(params) if isinstance(params, str) else dict(cast("dict[str, object]", params))
    )
    carry_from = params.get("carry_from")
    async with uow(tenant) as tx:
        for x in lines:
            await tx.session.execute(
                _INSERT_LINE,
                {
                    "t": tenant.tenant_id,
                    "set": set_id,
                    "pos": x.position,
                    "key": x.key,
                    "caption": x.caption[:200],
                    "group": x.group_key,
                    "cy": x.cy,
                    "py": x.py,
                    "change": x.change,
                    "pct": x.change_pct,
                    "evaluated": x.evaluated,
                    "over": x.over,
                    "derived": x.derived,
                    "status": None if x.derived else ("unexplained" if x.over else "within"),
                    "sources": list(x.sources),
                    "cell": x.cell,
                },
            )
        carried = 0
        if isinstance(carry_from, str):
            carried = await _carry_forward(tx, tenant, UUID(carry_from), set_id, lines)
        await tx.session.execute(
            _SUPERSEDE,
            {"new": set_id, "w": row["work_item_id"], "k": row["kind"], "s": row["stage"]},
        )
        done = await tx.session.scalar(
            _COMPLETE,
            {"id": set_id, "ih": result.inputs_hash, "ch": content_hash(lines), "bal": balanced},
        )
        if done is None:
            return "superseded"
        tx.record(
            "analytics.computed",
            target=Target(TARGET, set_id),
            after=Ref(version=int(cast(int, row["version_no"])), n=len(lines), m=carried),
        )
        tx.emit(
            AnalyticsComputed(
                analytics_set_id=set_id,
                engagement_id=cast(UUID, row["engagement_id"]),
                work_item_id=cast(UUID, row["work_item_id"]),
                version_no=int(cast(int, row["version_no"])),
            )
        )
    return "current"


async def _carry_forward(
    tx: UnitOfWork,
    tenant: TenantContext,
    old_set: UUID,
    new_set: UUID,
    lines: Sequence[ComputedLine],
) -> int:
    """AC-5.2: an explanation (and its acceptance) carries to the new version only where the
    line's over/within result is unchanged; a line that changed status goes stale."""
    session = tx.session
    old_lines = {
        str(r.fs_line_key): bool(r.over) for r in await session.execute(_LINES, {"set": old_set})
    }
    old_positions = {
        int(r.position): str(r.fs_line_key)
        for r in await session.execute(_LINES, {"set": old_set})
    }
    by_key = {x.key: x for x in lines}
    carried = 0
    for e in (await session.execute(_EXPLANATIONS, {"set": old_set})).mappings():
        key = old_positions.get(int(e["line_position"]))
        new = by_key.get(key) if key else None
        if new is None or not new.over or old_lines.get(key or "") != new.over:
            continue
        await session.execute(
            _INSERT_EXPLANATION,
            {
                "t": tenant.tenant_id,
                "set": new_set,
                "pos": new.position,
                "text": e["text"],
                "cites": list(e["citation_ids"] or []),
                "source": e["source"],
                "sug": e["suggestion_id"],
                "q": e["question_id"],
                "contact": e["answered_by_contact_id"],
                "by": e["authored_by"],
                "carried": e["id"],
                # An acceptance carries with its original time (it happened then).
                "accepted_by": e["accepted_by"],
                "accepted_at": e["accepted_at"],
            },
        )
        carried += 1
    return carried


@activity.defn(name="assurance.analytics.compute")
async def compute_activity(p: RunInput) -> str:
    tenant = TenantContext(UUID(p.tenant_id), "system", f"{SYSTEM_ACTOR}:{p.analytics_set_id}")
    return await compute_set(tenant, UUID(p.analytics_set_id))


@workflow.defn(name="FluxAnalyticsWorkflow")
class FluxAnalyticsWorkflow:
    """load the TB layer and PY → compute (`workpapers.compute.flux`) → persist the lines."""

    @workflow.run
    async def run(self, p: RunInput) -> str:
        return await workflow.execute_activity(
            "assurance.analytics.compute",
            p,
            result_type=str,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )


# --- reads ---------------------------------------------------------------------------------------


async def _explanations(tenant: TenantContext, set_id: UUID) -> dict[int, ExplanationView]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_EXPLANATIONS, {"set": set_id})).mappings().all()
    people = [cast(UUID, r[k]) for r in rows for k in ("authored_by", "accepted_by") if r[k]]
    names = await names_of(list(dict.fromkeys(people))) if people else {}
    out: dict[int, ExplanationView] = {}
    for r in rows:
        author = cast(UUID | None, r["authored_by"])
        accepted = cast(UUID | None, r["accepted_by"])
        answered = (
            cast(datetime, r["created_at"]).date() if r["source"] == "client_answer" else None
        )
        out[int(r["line_position"])] = ExplanationView(
            id=cast(UUID, r["id"]),
            text=str(r["text"]),
            citation_ids=tuple(cast("list[UUID]", r["citation_ids"] or [])),
            source=str(r["source"]),
            suggestion_id=cast(UUID | None, r["suggestion_id"]),
            authored_by=author,
            authored_by_name=names.get(author, "") if author else "",
            client_answered_on=answered,
            accepted_by=accepted,
            accepted_by_initials=initials(names.get(accepted, "")) if accepted else None,
        )
    return out


async def _client_names(
    tenant: TenantContext, set_id: UUID, explanations: dict[int, ExplanationView]
) -> dict[int, ExplanationView]:
    """A client answer reads "Client answer Sep 16 · Luis Ferrante": the answering contact."""
    from dataclasses import replace

    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT line_position, answered_by_contact_id FROM analytics_explanations "
                    "WHERE set_id = :set AND source = 'client_answer'"
                ),
                {"set": set_id},
            )
        ).all()
    contacts = {
        int(r.line_position): r.answered_by_contact_id for r in rows if r.answered_by_contact_id
    }
    if not contacts:
        return explanations
    names = await names_of(list(set(contacts.values())))
    return {
        pos: replace(e, authored_by_name=names.get(contacts[pos], ""))
        if pos in contacts and e.source == "client_answer"
        else e
        for pos, e in explanations.items()
    }


async def _expectations(tenant: TenantContext, set_id: UUID) -> dict[int, ExpectationView]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_EXPECTATIONS, {"set": set_id})).all()
    return {
        int(r.line_position): ExpectationView(r.pct_low, r.pct_high, r.low, r.high, str(r.basis))
        for r in rows
    }


async def set_view(ctx: AuthContext, set_id: UUID, *, authorised: bool = False) -> SetView:
    """`GET /v1/analytics-sets/{aid}`: lines, tallies, threshold facts and the TB tie."""
    row = await _set_row(ctx.tenant, set_id)
    engagement_id = cast(UUID, row["engagement_id"])
    resource = await _resource(ctx, engagement_id)
    if not authorised:
        await authorise(ctx, READ, resource)
    async with tenant_session(ctx.tenant) as session:
        raw = (await session.execute(_LINES, {"set": set_id})).all()
    explanations = await _client_names(ctx.tenant, set_id, await _explanations(ctx.tenant, set_id))
    expectations = await _expectations(ctx.tenant, set_id)
    lines: list[LineView] = []
    for r in raw:
        pos = int(r.position)
        explanation = explanations.get(pos)
        base = LineView(
            position=pos,
            fs_line_key=str(r.fs_line_key),
            caption=str(r.caption),
            group_key=str(r.group_key),
            cy=Decimal(r.cy),
            py=Decimal(r.py),
            change=Decimal(r.change),
            change_pct=None if r.change_pct is None else Decimal(r.change_pct),
            evaluated=bool(r.evaluated),
            over=bool(r.over),
            derived=bool(r.derived),
            status=None,
            explanation=explanation if bool(r.over) else None,
            expectation=expectations.get(pos),
            sources=tuple(r.sources or ()),
            cell=str(r.cell),
        )
        from dataclasses import replace

        lines.append(replace(base, status=line_status(base, base.explanation)))
    evaluated = [x for x in lines if x.evaluated]
    tallies = Tallies(
        lines=len(evaluated),
        over_threshold=sum(1 for x in evaluated if x.over),
        explained=sum(1 for x in evaluated if x.status in ("explained", "accepted")),
        unexplained=sum(1 for x in evaluated if x.status == "unexplained"),
        tb_balanced=bool(row["tb_balanced"]),
    )
    overall: Decimal | None = None
    if row["materiality_version_id"] is not None:
        from abacus.modules.assurance.materiality import versions_of

        found = [
            v
            for v in await versions_of(ctx.tenant, cast(UUID, row["work_item_id"]))
            if v.id == row["materiality_version_id"]
        ]
        overall = found[0].overall if found else None
    threshold = ThresholdFacts(
        pct=Decimal(str(row["threshold_pct"])),
        amount=Decimal(str(row["threshold_amount"])),
        materiality_version_id=cast(UUID | None, row["materiality_version_id"]),
        overall=overall,
        provisional=bool(row["provisional"]),
        decider_name=await _decider(ctx, engagement_id),
    )
    can = (
        await allowed_actions(ctx, resource, ACTIONS)
        if row["status"] == "current"
        else frozenset({"analytics.export"}) & await allowed_actions(ctx, resource, ACTIONS)
    )
    return SetView(
        id=set_id,
        engagement_id=engagement_id,
        work_item_id=cast(UUID, row["work_item_id"]),
        kind=cast(Kind, row["kind"]),
        stage=cast(Stage, row["stage"]),
        version_no=int(cast(int, row["version_no"])),
        status=str(row["status"]),
        basis_label=str(row["basis_label"]),
        threshold=threshold,
        tallies=tallies,
        lines=tuple(lines),
        engine_version=str(row["engine_version"]),
        inputs_hash=str(row["inputs_hash"] or ""),
        review_hash=review_hash(set_id, int(cast(int, row["version_no"])), lines),
        allowed_actions=tuple(a for a in ACTIONS if a in can),
        failure_code=cast(str | None, row["failure_code"]),
    )


async def provenance(ctx: AuthContext, set_id: UUID, position: int) -> Provenance:
    """SHL-09: the cell and its formula: an FS line adds its TB accounts; a subtotal its lines."""
    view = await set_view(ctx, set_id)
    line = next((x for x in view.lines if x.position == position), None)
    if line is None:
        raise NotFound("analytics_line")
    if line.derived:
        parts = [x for x in view.lines if x.group_key == line.group_key and not x.derived]
        formula = "=" + "+".join(x.cell for x in parts) if parts else "=0"
        return Provenance(line.cell, formula, tuple(x.fs_line_key for x in parts))
    formula = "=" + "+".join(f"TB!{code}" for code in line.sources) if line.sources else "=0"
    return Provenance(line.cell, formula, line.sources)


# --- explain and accept --------------------------------------------------------------------------


async def _current(ctx: AuthContext, set_id: UUID, action: str) -> dict[str, object]:
    row = await _set_row(ctx.tenant, set_id)
    await authorise(ctx, action, await _resource(ctx, cast(UUID, row["engagement_id"])))
    if row["status"] != "current":
        raise SetNotCurrent(facts={"status": str(row["status"])})
    return row


async def explain(
    ctx: AuthContext,
    set_id: UUID,
    position: int,
    *,
    text_: str,
    citation_ids: Sequence[UUID],
    suggestion_id: UUID | None = None,
) -> LineView:
    """`PUT …/lines/{pos}/explanation`: 422 `explanation_uncited` unless every citation is
    verified by code and still valid on the engagement (INV-2)."""
    from abacus.modules.evidence.api import supported_citations

    _person(ctx, "analytics.explain")
    row = await _current(ctx, set_id, "analytics.explain")
    engagement_id = cast(UUID, row["engagement_id"])
    view = await set_view(ctx, set_id, authorised=True)
    line = next((x for x in view.lines if x.position == position), None)
    if line is None:
        raise NotFound("analytics_line")
    if not line.over:
        raise LineNotOver(facts={"position": position})
    cited = list(dict.fromkeys(citation_ids))
    supported = (
        await supported_citations(ctx.tenant, engagement_id, cited) if cited else frozenset[UUID]()
    )
    if not cited or any(c not in supported for c in cited):
        raise ExplanationUncited(facts={"position": position})
    async with uow(ctx.tenant) as tx:
        made = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_EXPLANATION,
                {
                    "t": ctx.tenant_id,
                    "set": set_id,
                    "pos": position,
                    "text": text_.strip(),
                    "cites": cited,
                    "source": "agent" if suggestion_id else "staff",
                    "sug": suggestion_id,
                    "q": None,
                    "contact": None,
                    "by": ctx.user_id,
                    "carried": None,
                    "accepted_by": None,
                    "accepted_at": None,
                },
            ),
        )
        tx.record(
            "explanation.recorded",
            target=Target(TARGET, set_id),
            after=Ref(explanation=made, position=position, n=len(cited)),
        )
        tx.emit(
            AnalyticsExplanationRecorded(
                analytics_set_id=set_id, engagement_id=engagement_id, explanation_id=made
            )
        )
    found = await set_view(ctx, set_id, authorised=True)
    return next(x for x in found.lines if x.position == position)


async def accept(
    ctx: AuthContext, set_id: UUID, *, line_positions: Sequence[int], seen_hash: str
) -> SetView:
    """SHL-10: a manager or the partner accepts the explanations on these lines; never their
    author (`not_preparer_of_target`); `seen_hash` is the review hash they were shown."""
    _person(ctx, "analytics.accept")
    row = await _set_row(ctx.tenant, set_id)
    if row["status"] != "current":
        raise SetNotCurrent(facts={"status": str(row["status"])})
    engagement_id = cast(UUID, row["engagement_id"])
    await authorise(ctx, READ, await _resource(ctx, engagement_id))
    view = await set_view(ctx, set_id, authorised=True)
    if seen_hash != view.review_hash:
        raise ContentChanged(facts={"analytics_set": str(set_id)})
    chosen = [x for x in view.lines if x.position in set(line_positions)]
    if len(chosen) != len(set(line_positions)):
        raise NotFound("analytics_line")
    pending = [x for x in chosen if x.status == "explained" and x.explanation is not None]
    if not pending:
        raise LineNotOver(facts={"positions": len(chosen)})
    authors = frozenset(
        x.explanation.authored_by
        for x in pending
        if x.explanation is not None and x.explanation.authored_by is not None
    )
    await authorise(ctx, "analytics.accept", await _resource(ctx, engagement_id, authors))
    async with uow(ctx.tenant) as tx:
        accepted = 0
        for x in pending:
            if x.explanation is None:
                continue
            if await tx.session.scalar(_ACCEPT, {"id": x.explanation.id, "by": ctx.user_id}):
                accepted += 1
        tx.record(
            "explanation.accepted",
            target=Target(TARGET, set_id),
            after=Ref(n=accepted),
        )
        tx.emit(
            AnalyticsExplanationAccepted(
                analytics_set_id=set_id, engagement_id=engagement_id, accepted=accepted
            )
        )
    return await set_view(ctx, set_id, authorised=True)


# --- client questions ----------------------------------------------------------------------------


@dataclass(frozen=True)
class QuestionCard:
    template_key: str
    text: str


async def send_client_questions(
    ctx: AuthContext,
    set_id: UUID,
    *,
    line_positions: Sequence[int],
    cards: Sequence[QuestionCard],
    recipient_contact_id: UUID,
) -> tuple[UUID, datetime]:
    """DV-4: firm-templated wording a person edited, sent by that person to the client contact
    as one T-02 questionnaire (POR-05); each question remembers its line."""
    from abacus.kernel.clock import system_now
    from abacus.modules.requests.api import create_questionnaire, draft_question, send_question

    _person(ctx, "client_question.send")
    row = await _current(ctx, set_id, "client_question.send")
    if len(cards) != len(line_positions):
        raise QuestionCardsMismatch(facts={"cards": len(cards), "lines": len(line_positions)})
    view = await set_view(ctx, set_id, authorised=True)
    by_pos = {x.position: x for x in view.lines}
    for pos in line_positions:
        line = by_pos.get(pos)
        if line is None:
            raise NotFound("analytics_line")
        if line.status != "unexplained":
            raise LineNotOver(facts={"position": pos})
    created = await create_questionnaire(
        ctx,
        kind="analytics_question",
        work_item_id=cast(UUID, row["work_item_id"]),
        title=f"Questions about {view.basis_label}",
        addressed_to_contact_id=recipient_contact_id,
        due_on=None,
        engagement_id=cast(UUID, row["engagement_id"]),
    )
    asked: list[tuple[int, UUID, str]] = []
    for pos, card in zip(line_positions, cards, strict=True):
        drafted = await draft_question(
            ctx,
            created.id,
            section=by_pos[pos].caption,
            type_="long_text",
            client_wording=card.text.strip(),
            help_text=None,
            linked_request_item_id=None,
        )
        await send_question(ctx, drafted.id)
        asked.append((pos, drafted.id, card.template_key))
    async with uow(ctx.tenant) as tx:
        for pos, question_id, template in asked:
            await tx.session.execute(
                _INSERT_QUESTION,
                {
                    "t": ctx.tenant_id,
                    "set": set_id,
                    "pos": pos,
                    "qn": created.id,
                    "q": question_id,
                    "tpl": template,
                    "by": ctx.user_id,
                },
            )
        tx.record(
            "client_question.sent",
            target=Target(TARGET, set_id),
            after=Ref(questionnaire=created.id, n=len(asked)),
        )
        tx.emit(
            ClientQuestionSent(
                analytics_set_id=set_id,
                engagement_id=cast(UUID, row["engagement_id"]),
                questionnaire_id=created.id,
            )
        )
    return created.id, system_now()


async def on_questionnaire_answered(event: OutboxEvent) -> None:
    """A client's answer to an analytics question becomes the line's `client_answer`
    explanation (it counts once a manager accepts it). Other questions pass; idempotent."""
    from abacus.modules.requests.api import answer_fact

    question_id = event.payload.get("question_id")
    answer_id = event.payload.get("answer_id")
    if question_id is None or answer_id is None:
        return
    tenant = TenantContext(event.tenant_id, "system", f"{SYSTEM_ACTOR}:answer")
    async with tenant_session(tenant) as session:
        link = (await session.execute(_QUESTION_OF, {"q": UUID(str(question_id))})).first()
    if link is None or link.status != "current":
        return
    fact = await answer_fact(tenant, UUID(str(answer_id)))
    if fact is None or not fact.text.strip():
        return
    async with uow(tenant) as tx:
        seen = await tx.session.scalar(
            text(
                "SELECT 1 FROM analytics_explanations WHERE set_id = :s AND line_position = :p "
                "AND question_id = :q AND text = :x"
            ),
            {
                "s": link.set_id,
                "p": link.line_position,
                "q": fact.question_id,
                "x": fact.text[:1000],
            },
        )
        if seen:
            return
        made = cast(
            UUID,
            await tx.session.scalar(
                _INSERT_EXPLANATION,
                {
                    "t": event.tenant_id,
                    "set": link.set_id,
                    "pos": link.line_position,
                    "text": fact.text.strip()[:1000],
                    "cites": [],
                    "source": "client_answer",
                    "sug": None,
                    "q": fact.question_id,
                    "contact": fact.answered_by,
                    "by": None,
                    "carried": None,
                    "accepted_by": None,
                    "accepted_at": None,
                },
            ),
        )
        tx.record(
            "client_question.answered",
            target=Target(TARGET, cast(UUID, link.set_id)),
            after=Ref(explanation=made, position=int(link.line_position)),
        )
        tx.emit(
            AnalyticsExplanationRecorded(
                analytics_set_id=cast(UUID, link.set_id),
                engagement_id=cast(UUID, link.engagement_id),
                explanation_id=made,
            )
        )


async def on_materiality_decided(event: OutboxEvent) -> None:
    """AC-5.2: a decided materiality re-thresholds each Current preliminary set as a new version
    (the old one is never edited). Idempotent on the event."""
    work_item = event.payload.get("work_item_id")
    if work_item is None:
        return
    work_item_id = UUID(str(work_item))
    tenant = TenantContext(event.tenant_id, "system", f"{SYSTEM_ACTOR}:materiality")
    async with tenant_session(tenant) as session:
        current = [r.id for r in await session.execute(_CURRENT_PRELIMINARY, {"w": work_item_id})]
        done = (
            await session.execute(_BY_EVENT, {"w": work_item_id, "ev": str(event.event_id)})
        ).first()
    if not current or done is not None:
        return
    threshold = await threshold_for(tenant, work_item_id)
    for set_id in current:
        row = await _set_row(tenant, cast(UUID, set_id))
        await _start(
            tenant,
            engagement_id=cast(UUID, row["engagement_id"]),
            work_item_id=work_item_id,
            kind="audit_flux",
            stage="preliminary",
            trial_balance_id=cast(UUID, row["cy_trial_balance_id"]),
            layer=str(row["cy_layer"]),
            py_source=str(row["py_source"]),
            threshold=threshold,
            created_by=cast(UUID, row["created_by"]),
            params={"carry_from": str(set_id), "event_id": str(event.event_id)},
        )


# --- prior-year figures and export ---------------------------------------------------------------


@dataclass(frozen=True)
class PriorYearFigure:
    fs_line_key: str
    amount: Decimal
    citation_id: UUID | None


async def put_prior_year_figures(
    ctx: AuthContext, work_item_id: UUID, *, source: str, figures: Sequence[PriorYearFigure]
) -> int:
    """An import (each figure cited by a verified citation) or the prior engagement's figures as
    the work item's trial balance carries its prior period; a new numbered import each time."""
    from abacus.modules.engagements.api import work_item_engagement
    from abacus.modules.evidence.api import supported_citations
    from abacus.modules.ledger import api as ledger

    _person(ctx, "analytics.configure")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    rows: list[PriorYearFigure]
    if source == "import":
        if not figures:
            raise DomainInvalid(facts={"field": "figures"})
        cited = [f.citation_id for f in figures if f.citation_id is not None]
        supported = (
            await supported_citations(ctx.tenant, engagement_id, cited)
            if cited
            else frozenset[UUID]()
        )
        if any(f.citation_id is None or f.citation_id not in supported for f in figures):
            raise ExplanationUncited(facts={"field": "citation_id"})
        rows = list({f.fs_line_key: f for f in figures}.values())
    else:
        tbs = await ledger.engagement_trial_balances(ctx.tenant, engagement_id)
        if not tbs:
            raise NotFound("trial_balance")
        latest = max(tbs, key=lambda t: t.period_end)
        view = await ledger.mapping_view(ctx.tenant, engagement_id, latest.id)
        if view is None:
            raise NotFound("mapping_set")
        statements = ledger.build_statements(view.groupings, view.accounts, "unadjusted")
        rows = [
            PriorYearFigure(line.key, line.py, None)
            for g in statements.groups
            for line in g.lines
            if line.py is not None
        ]
    async with uow(ctx.tenant) as tx:
        number = int(cast(int, await tx.session.scalar(_PY_NEXT, {"w": work_item_id})))
        for f in rows:
            await tx.session.execute(
                _PY_INSERT,
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "w": work_item_id,
                    "n": number,
                    "source": source,
                    "key": f.fs_line_key,
                    "amount": f.amount,
                    "cite": f.citation_id,
                    "by": ctx.user_id,
                },
            )
        tx.record(
            "prior_year_figures.imported",
            target=Target("work_item", work_item_id),
            after=Ref(n=len(rows), version=number),
        )
    return len(rows)


async def workbook_of(ctx: AuthContext, set_id: UUID) -> bytes:
    """The deterministic workbook: header, then each line in position (D is the current year)."""
    row = await _set_row(ctx.tenant, set_id)
    await authorise(
        ctx, "analytics.export", await _resource(ctx, cast(UUID, row["engagement_id"]))
    )
    view = await set_view(ctx, set_id, authorised=True)
    header: list[Cell] = ["Line", "Caption", "Group", "Current", "Prior", "Change", "Change %",
                            "Result", "Status", "Explanation"]  # fmt: skip
    body: list[list[Cell]] = [header]
    for x in view.lines:
        body.append(
            [
                x.position,
                x.caption,
                x.group_key,
                x.cy,
                x.py,
                x.change,
                "" if x.change_pct is None else x.change_pct,
                "Derived" if x.derived else ("Over" if x.over else "Within"),
                x.status or "",
                x.explanation.text if x.explanation else "",
            ]
        )
    facts: list[list[Cell]] = [
        ["Basis", view.basis_label],
        ["Version", view.version_no],
        ["Threshold", f"{view.threshold.pct}% and {view.threshold.amount}"],
        ["Engine", view.engine_version],
        ["Inputs hash", view.inputs_hash],
    ]
    return workbook(
        [
            Sheet("Analytics", body),
            Sheet("About", facts),
        ]
    )


# --- HOME-02: the manager's acceptance gate (C13) ------------------------------------------------

GATE: Final = "analytics_explanation_acceptance"
_WAITING: Final = text(
    "SELECT DISTINCT s.id, s.engagement_id, s.work_item_id FROM analytics_sets s "
    "JOIN analytics_explanations e ON e.set_id = s.id "
    "JOIN analytics_lines l ON l.set_id = e.set_id AND l.position = e.line_position "
    "WHERE s.status = 'current' AND l.over AND e.accepted_by IS NULL"
)


async def acceptances_due(tenant: TenantContext, engagement_id: UUID | None) -> list[object]:
    """A Current set with an explained, unaccepted line waits on the engagement's managers."""
    from abacus.modules.review.api import OpenGate

    async with tenant_session(tenant) as session:
        rows = (await session.execute(_WAITING)).mappings().all()
    return [
        OpenGate(r["id"], r["engagement_id"], role="manager", work_item_id=r["work_item_id"])
        for r in rows
        if engagement_id is None or r["engagement_id"] == engagement_id
    ]


def register_acceptance_gate() -> None:
    from abacus.modules.review.api import GateSource, register_gate_source

    register_gate_source(
        GateSource(
            TARGET,
            "decision",
            READ,
            frozenset(
                {
                    "analytics.computed",
                    "analytics.explanation_recorded",
                    "analytics.explanation_accepted",
                }
            ),
            acceptances_due,  # type: ignore[arg-type] -- returns OpenGate rows
        )
    )


WORKFLOWS: Final[dict[type, str]] = {FluxAnalyticsWorkflow: "interactive"}
ACTIVITIES: Final[tuple[object, ...]] = (compute_activity,)
SUBSCRIPTIONS: Final = {
    "materiality.decided": on_materiality_decided,
    "questionnaire.answered": on_questionnaire_answered,
}
