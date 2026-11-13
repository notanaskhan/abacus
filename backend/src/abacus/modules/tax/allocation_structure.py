"""The allocation structure service (T-05-T41; T-05 F5, §4.2, §4.3; TXP-06; SPEC-651 AC-5.1 to
AC-5.4; ADR-005, ADR-050; DEC-4701, DEC-4702). Amber. Reads and writes the T-05-T17 tables
(`allocation_structures`, `allocation_rungs`, `allocation_results`, 0821) of this module only.

- **Versions.** Every save is a new insert-only version (`version_no` + 1); `expected_version` is
  the latest version number the person read (0 before any), anything else is 409
  `structure_version_conflict`. A version's `content_hash` covers what a sign-off approves: the
  kind, method, convention, income, the segment amounts and the rungs.
- **Who drafts.** `allocation_structure.edit` (matrix) and, in this service, the person's role on
  the engagement must be a manager or a partner (T-05 §4.3: "level_in manager, partner"); a senior
  or staff save is 403 `structure_editor_required`. An agent never drafts: the agreement reader
  proposes through C17 (`tax.propose_allocation_structure`, T-05-T36), and a person's approval of
  that proposal adopts it as a version Pending approval (`proposed_by_kind = 'agent'`).
- **Preview.** `preview` runs the engine on a draft and persists nothing (TXP-06 d's live
  preview; the back-solve shows Pending until Save).
- **Approval.** An L3 sign-off (P-04, C3) on the `allocation_structure` reviewable with the
  version's hash as `seen_hash`. P-04 refuses an agent (R-SO-1), a level the person's role does not
  carry (`level_not_permitted`, staff) and the version's own preparer (R-SO-3, DEC-4702: the
  person who drafted a version, or who approved the agent's proposal, prepares it and signs L1;
  another manager or partner approves it at L3). The service then writes the person's own
  `approved` version row (the 0821 human-only CHECK) and starts a re-run of the capital and K-1
  groups (`capital`, `k1s`) as that person. A run already open is left alone (the re-run waits).
- **Status.** The newest version's status; older versions read `superseded`.
- **Compute.** Code computes (ADR-050): straight percentage through E5 part 1 (ownership periods,
  the interest transfers and the convention; interim closing takes the segments' amounts from the
  draft or from 04 Allocation's column D, written by T-05-T40's `interim_closing_706d`),
  the targeted waterfall through E5 part 2 (beginning capital from 05 Capital's column B).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainForbidden, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, engagement_role_of
from abacus.modules.review.api import (
    Reviewable,
    ReviewableFacts,
    content_hash,
    register_reviewable,
    register_reviewable_facts,
)
from abacus.modules.tax.compute.entity.allocation import (
    AllocationInvalid,
    Convention,
    Method,
    allocate_item,
    segments,
)
from abacus.modules.tax.compute.entity.waterfall import (
    RuleType,
    Rung,
    WaterfallInvalid,
    WaterfallPartner,
    run_waterfall,
)

TARGET: Final = "allocation_structure"
Kind = Literal["straight_percentage", "targeted_waterfall"]
Status = Literal["editing", "pending_approval", "approved", "superseded"]
RULE_TYPES: Final[frozenset[str]] = frozenset(
    {"straight_pct", "return_of_capital", "preferred_return", "catch_up", "promote", "residual"}
)
# The rung's one percentage, by rule (TXP-06 d's inline editor edits these).
PERCENT_PARAM: Final[Mapping[str, str]] = {
    "preferred_return": "rate",
    "catch_up": "target",
    "promote": "gp",
}
EDITOR_ROLES: Final = frozenset({"manager", "engagement_partner"})
RERUN_GROUPS: Final = ("capital", "k1s")
SEGMENT_SHEET: Final = "04"  # 04 Allocation: row n+1 is segment n; D is its closed-books amount
SEGMENT_AMOUNT_COL: Final = "D"
ZERO: Final = Decimal(0)


class StructureVersionConflict(DomainConflict):
    """The structure moved since the person read it: reload and re-apply."""

    code = "structure_version_conflict"


class StructureNotPending(DomainConflict):
    """Only a version Pending approval is approved; the newest version is not one."""

    code = "structure_not_pending"


class StructureEditorRequired(DomainForbidden):
    """A manager or a partner on the engagement drafts the structure (T-05 §4.3)."""

    code = "structure_editor_required"


class StructureInvalid(DomainInvalid):
    """The engine cannot run the structure; `facts.code` says why (never a partner's figures)."""

    code = "structure_invalid"


# --- the draft and its compute (pure) ------------------------------------------------------------


@dataclass(frozen=True)
class DraftRung:
    priority: int
    rule_type: str
    params: Mapping[str, str] = field(default_factory=dict[str, str])
    citation_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class Draft:
    kind: Kind
    method: Method = "interim_closing"
    convention: Convention = "calendar_day"
    income: Decimal | None = None
    segment_amounts: tuple[Decimal, ...] = ()
    rungs: tuple[DraftRung, ...] = ()
    citation_ids: tuple[UUID, ...] = ()

    def hash(self) -> str:
        """What a sign-off approves (citations are evidence for the reader, not the structure)."""
        return content_hash(
            {
                "kind": self.kind,
                "method": self.method,
                "convention": self.convention,
                "income": None if self.income is None else format(self.income, "f"),
                "segment_amounts": [format(a, "f") for a in self.segment_amounts],
                "rungs": [
                    {"priority": r.priority, "rule_type": r.rule_type, "params": dict(r.params)}
                    for r in sorted(self.rungs, key=lambda r: r.priority)
                ],
            }
        )


@dataclass(frozen=True)
class PartnerFacts:
    id: UUID
    name: str
    kind: str  # gp, lp, member, shareholder
    beginning_capital: Decimal = ZERO


@dataclass(frozen=True)
class PeriodFacts:
    partner_id: UUID
    starts_on: date
    ends_on: date
    profit_pct: Decimal


@dataclass(frozen=True)
class ResultRow:
    partner_id: UUID
    period_key: str
    rung_priority: int | None
    amount: Decimal


@dataclass(frozen=True)
class PeriodOut:
    key: str
    starts_on: date | None
    ends_on: date | None
    amount: Decimal


@dataclass(frozen=True)
class Computed:
    results: tuple[ResultRow, ...]
    periods: tuple[PeriodOut, ...]
    totals: Mapping[UUID, Decimal]
    total: Decimal
    distributable: Decimal | None
    engine_name: str
    engine_version: str
    inputs_hash: str
    checks: Mapping[str, bool]
    gp_profit_percent: Decimal | None = None


def rung_params(
    rule_type: str, percentage: Decimal | None, amount: Decimal | None
) -> dict[str, str]:
    """The contract's rung (one percentage, one amount) as the engine's params."""
    out: dict[str, str] = {}
    key = PERCENT_PARAM.get(rule_type)
    if key is not None and percentage is not None:
        out[key] = format(percentage, "f")
    if rule_type == "preferred_return" and amount is not None:
        out["days"] = format(amount, "f")  # a part year, in days; absent is a full year
    return out


def _straight(
    draft: Draft,
    year: int,
    periods: Sequence[PeriodFacts],
    transfers: Sequence[date],
    sheet_amounts: Sequence[Decimal],
) -> Computed:
    starts = sorted({p.starts_on for p in periods})
    if not starts:
        raise StructureInvalid(facts={"code": "ownership_periods_required"})
    if len(starts) - 1 != len(transfers):
        raise StructureInvalid(facts={"code": "periods_do_not_match_transfers"})
    by_transfer: list[tuple[date | None, Mapping[str, Decimal]]] = []
    for n, start in enumerate(starts):
        interests = {str(p.partner_id): p.profit_pct for p in periods if p.starts_on == start}
        by_transfer.append((None if n == 0 else transfers[n - 1], interests))
    try:
        segs = segments(date(year, 1, 1), date(year, 12, 31), by_transfer, draft.convention)
        given = draft.segment_amounts or tuple(sheet_amounts[: len(segs)])
        if draft.method == "interim_closing":
            if len(given) != len(segs):
                raise StructureInvalid(facts={"code": "segment_amounts_required"})
            total = sum(given, ZERO)
            if draft.income is not None and draft.income != total:
                raise StructureInvalid(facts={"code": "segments_do_not_sum_to_the_year"})
            found = allocate_item(
                total, segs, method="interim_closing", convention=draft.convention,
                segment_amounts=given,
            )  # fmt: skip
        else:
            if draft.income is None:
                raise StructureInvalid(facts={"code": "income_required"})
            found = allocate_item(
                draft.income, segs, method="proration", convention=draft.convention
            )
    except AllocationInvalid as error:
        raise StructureInvalid(facts={"code": error.code}) from None
    results = tuple(
        ResultRow(UUID(partner), f"p{n}", None, amount)
        for n, shares in enumerate(found.shares, start=1)
        for partner, amount in shares.items()
        if amount != 0
    )
    period_rows = tuple(
        PeriodOut(f"p{n}", s.start, s.end, a)
        for n, (s, a) in enumerate(
            zip(found.segments, found.segment_amounts, strict=True), start=1
        )
    )
    totals = {UUID(p): t for p, t in found.totals.items()}
    checks = {
        "periods_foot": all(
            sum(shares.values(), ZERO) == amount
            for shares, amount in zip(found.shares, found.segment_amounts, strict=True)
        ),
        "partners_foot": sum(totals.values(), ZERO) == found.total,
    }
    return Computed(
        results, period_rows, totals, found.total, None, found.stamp.engine_name,
        found.stamp.engine_version, found.stamp.inputs_hash, checks,
    )  # fmt: skip


def _waterfall(draft: Draft, partners: Sequence[PartnerFacts]) -> Computed:
    if draft.income is None:
        raise StructureInvalid(facts={"code": "income_required"})
    rungs: list[Rung] = []
    for r in sorted(draft.rungs, key=lambda r: r.priority):
        if r.rule_type not in RULE_TYPES:
            raise StructureInvalid(facts={"code": "unknown_rule_type"})
        rungs.append(Rung(r.priority, cast(RuleType, r.rule_type), dict(r.params)))
    try:
        found = run_waterfall(
            [
                WaterfallPartner(str(p.id), "gp" if p.kind == "gp" else "lp", p.beginning_capital)
                for p in partners
            ],
            rungs,
            draft.income,
        )
    except (WaterfallInvalid, InvalidOperation) as error:
        code = error.code if isinstance(error, WaterfallInvalid) else "params_invalid"
        raise StructureInvalid(facts={"code": code}) from None
    results = tuple(
        ResultRow(UUID(partner), "year", rung.priority, amount)
        for rung in found.rungs
        for partner, amount in rung.shares.items()
        if amount != 0
    )
    periods = tuple(PeriodOut(f"r{r.priority}", None, None, r.amount) for r in found.rungs)
    return Computed(
        results, periods, {UUID(p): v for p, v in found.plugs.items()}, found.income,
        found.distributable, found.stamp.engine_name, found.stamp.engine_version,
        found.stamp.inputs_hash, dict(found.checks), found.gp_profit_percent,
    )  # fmt: skip


def compute(
    draft: Draft,
    *,
    year: int,
    partners: Sequence[PartnerFacts],
    periods: Sequence[PeriodFacts],
    transfers: Sequence[date],
    sheet_amounts: Sequence[Decimal] = (),
) -> Computed:
    """The structure's results by code (never a model; ADR-050)."""
    if draft.method == "proration" and draft.convention != "calendar_day":
        raise StructureInvalid(facts={"code": "proration_is_calendar_day_only"})
    if len({r.priority for r in draft.rungs}) != len(draft.rungs):
        raise StructureInvalid(facts={"code": "duplicate_priority"})
    if draft.kind == "straight_percentage":
        return _straight(draft, year, periods, transfers, sheet_amounts)
    return _waterfall(draft, partners)


# --- reads ---------------------------------------------------------------------------------------

_STRUCTURES: Final = text(
    "SELECT id, version_no, status, kind, method, convention, income_to_allocate, distributable, "
    "proposed_by_kind, proposal_id, content_hash, engine_name, engine_version, inputs_hash, "
    "citation_ids, supersedes_id, decided_actor_kind, decided_actor_id, engagement_id, "
    "work_item_id, created_at FROM allocation_structures WHERE work_item_id = :r "
    "ORDER BY version_no DESC"
)
_STRUCTURE: Final = text(
    "SELECT id, version_no, status, kind, method, convention, income_to_allocate, distributable, "
    "proposed_by_kind, proposal_id, content_hash, engine_name, engine_version, inputs_hash, "
    "citation_ids, supersedes_id, decided_actor_kind, decided_actor_id, engagement_id, "
    "work_item_id, created_at FROM allocation_structures WHERE id = :i"
)
_RUNGS: Final = text(
    "SELECT priority, rule_type, params FROM allocation_rungs WHERE structure_id = :s "
    "ORDER BY priority"
)
_RESULTS: Final = text(
    "SELECT partner_id, period_key, rung_priority, amount FROM allocation_results "
    "WHERE structure_id = :s ORDER BY period_key, rung_priority NULLS FIRST, partner_id"
)
_PARTNERS: Final = text(
    "SELECT id, kind, display_name FROM partners WHERE work_item_id = :r "
    "ORDER BY ord, display_name"
)
_PERIODS: Final = text(
    "SELECT partner_id, period_from, period_to, profit_pct FROM ownership_periods "
    "WHERE work_item_id = :r ORDER BY period_from, partner_id"
)
_TRANSFERS: Final = text(
    "SELECT DISTINCT transfer_date FROM interest_transfers WHERE work_item_id = :r "
    "ORDER BY transfer_date"
)
_RETURNS_OF: Final = text(
    "SELECT DISTINCT ON (work_item_id) id, work_item_id, version_no, status, content_hash, "
    "supersedes_id FROM allocation_structures WHERE engagement_id = :e "
    "ORDER BY work_item_id, version_no DESC"
)


@dataclass(frozen=True)
class StructureRow:
    id: UUID
    version_no: int
    status: Status
    kind: Kind
    method: Method
    convention: Convention
    income: Decimal | None
    distributable: Decimal | None
    proposed_by_kind: Literal["human", "agent"]
    proposal_id: UUID | None
    content_hash: str
    citation_ids: tuple[UUID, ...]
    supersedes_id: UUID | None
    actor_kind: str
    actor_id: str
    engagement_id: UUID
    work_item_id: UUID

    @property
    def sign_off_target(self) -> UUID:
        """The version a sign-off names: an approved row's is the version it approved."""
        if self.status == "approved" and self.supersedes_id is not None:
            return self.supersedes_id
        return self.id


def _row(r: object) -> StructureRow:
    m = cast(Mapping[str, object], r)
    return StructureRow(
        id=cast(UUID, m["id"]),
        version_no=int(cast(int, m["version_no"])),
        status=cast(Status, m["status"]),
        kind=cast(Kind, m["kind"]),
        method=cast(Method, m["method"]),
        convention=cast(Convention, m["convention"]),
        income=cast(Decimal | None, m["income_to_allocate"]),
        distributable=cast(Decimal | None, m["distributable"]),
        proposed_by_kind=cast(Literal["human", "agent"], m["proposed_by_kind"]),
        proposal_id=cast(UUID | None, m["proposal_id"]),
        content_hash=str(m["content_hash"]),
        citation_ids=tuple(cast(list[UUID], m["citation_ids"] or [])),
        supersedes_id=cast(UUID | None, m["supersedes_id"]),
        actor_kind=str(m["decided_actor_kind"] or ""),
        actor_id=str(m["decided_actor_id"] or ""),
        engagement_id=cast(UUID, m["engagement_id"]),
        work_item_id=cast(UUID, m["work_item_id"]),
    )


@dataclass(frozen=True)
class StructureView:
    row: StructureRow | None
    status: Status
    rungs: tuple[DraftRung, ...]
    results: tuple[ResultRow, ...]
    partners: tuple[PartnerFacts, ...]
    latest_version: int


async def versions(tenant: TenantContext, return_id: UUID) -> list[StructureRow]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_STRUCTURES, {"r": return_id})).mappings().all()
    return [_row(r) for r in rows]


async def partners_of(tenant: TenantContext, return_id: UUID) -> list[PartnerFacts]:
    from abacus.modules.tax import entity_schedules as es

    async with tenant_session(tenant) as session:
        rows = (await session.execute(_PARTNERS, {"r": return_id})).mappings().all()
    values = await es.workbook_values(tenant, return_id)
    capital = {c.name: c.beginning for c in es.capital_rows(values, return_id, {})}
    return [
        PartnerFacts(
            r["id"],
            str(r["display_name"]),
            str(r["kind"]),
            capital.get(str(r["display_name"]), ZERO),
        )
        for r in rows
    ]


async def ownership_of(
    tenant: TenantContext, return_id: UUID
) -> tuple[list[PeriodFacts], list[date]]:
    async with tenant_session(tenant) as session:
        periods = (await session.execute(_PERIODS, {"r": return_id})).mappings().all()
        transfers = (await session.execute(_TRANSFERS, {"r": return_id})).scalars().all()
    return (
        [
            PeriodFacts(
                p["partner_id"], p["period_from"], p["period_to"], Decimal(p["profit_pct"])
            )
            for p in periods
        ],
        list(transfers),
    )


async def sheet_segment_amounts(tenant: TenantContext, return_id: UUID) -> list[Decimal]:
    """04 Allocation's closed-books amounts by segment (T-05-T40's `interim_closing_706d`)."""
    from abacus.modules.tax import entity_schedules as es

    values = await es.workbook_values(tenant, return_id)
    out: list[Decimal] = []
    n = 2
    while f"{SEGMENT_SHEET}!{SEGMENT_AMOUNT_COL}{n}" in values:
        out.append(es.dec(values, f"{SEGMENT_SHEET}!{SEGMENT_AMOUNT_COL}{n}"))
        n += 1
    return out


def status_of(row: StructureRow, newest: StructureRow) -> Status:
    return row.status if row.id == newest.id else "superseded"


async def view(
    tenant: TenantContext, return_id: UUID, version: int | None = None
) -> StructureView:
    """The newest version (or the one asked for) with its rungs and stored results. The caller
    authorised `allocation_structure.read` on the return."""
    found = await versions(tenant, return_id)
    partners = tuple(await partners_of(tenant, return_id))
    if not found:
        return StructureView(None, "editing", (), (), partners, 0)
    row = (
        found[0] if version is None else next((r for r in found if r.version_no == version), None)
    )
    if row is None:
        raise NotFound(TARGET)
    async with tenant_session(tenant) as session:
        rungs = (await session.execute(_RUNGS, {"s": row.id})).mappings().all()
        results = (await session.execute(_RESULTS, {"s": row.id})).mappings().all()
    return StructureView(
        row=row,
        status=status_of(row, found[0]),
        rungs=tuple(
            DraftRung(int(r["priority"]), str(r["rule_type"]), dict(r["params"] or {}))
            for r in rungs
        ),
        results=tuple(
            ResultRow(
                r["partner_id"], str(r["period_key"]), r["rung_priority"], Decimal(r["amount"])
            )
            for r in results
        ),
        partners=partners,
        latest_version=found[0].version_no,
    )


async def computed_for(
    tenant: TenantContext, return_id: UUID, year: int, draft: Draft
) -> Computed:
    partners = await partners_of(tenant, return_id)
    periods, transfers = await ownership_of(tenant, return_id)
    sheet = [] if draft.segment_amounts else await sheet_segment_amounts(tenant, return_id)
    return compute(
        draft, year=year, partners=partners, periods=periods, transfers=transfers,
        sheet_amounts=sheet,
    )  # fmt: skip


async def preview(ctx: AuthContext, return_id: UUID, year: int, draft: Draft) -> Computed:
    """TXP-06 d: the engine on an unsaved draft; nothing is written."""
    return await computed_for(ctx.tenant, return_id, year, draft)


# --- writes --------------------------------------------------------------------------------------

_INSERT_STRUCTURE: Final = text(
    "INSERT INTO allocation_structures (tenant_id, engagement_id, work_item_id, version_no, "
    "status, kind, method, convention, income_to_allocate, distributable, proposed_by_kind, "
    "proposal_id, content_hash, engine_name, engine_version, inputs_hash, citation_ids, "
    "supersedes_id) VALUES (:t, :e, :r, :v, :status, :kind, :method, :convention, :income, :dist, "
    ":by, :proposal, :hash, :engine, :engine_version, :inputs, :citations, :supersedes) "
    "RETURNING id"
)
_INSERT_RUNG: Final = text(
    "INSERT INTO allocation_rungs (tenant_id, engagement_id, work_item_id, structure_id, "
    "priority, rule_type, params) VALUES (:t, :e, :r, :s, :p, :rule, CAST(:params AS jsonb))"
)
_INSERT_RESULT: Final = text(
    "INSERT INTO allocation_results (tenant_id, engagement_id, work_item_id, structure_id, "
    "partner_id, period_key, rung_priority, amount) VALUES (:t, :e, :r, :s, :partner, :period, "
    ":rung, :amount)"
)
_LOCK: Final = text("SELECT pg_advisory_xact_lock(hashtextextended(:k, 0))")


async def _insert_version(
    tx: object,
    tenant_id: UUID,
    engagement_id: UUID,
    return_id: UUID,
    version_no: int,
    status: Status,
    draft: Draft,
    found: Computed | None,
    *,
    by: Literal["human", "agent"],
    proposal_id: UUID | None = None,
    supersedes: UUID | None = None,
) -> UUID:
    import json

    from abacus.kernel.uow import UnitOfWork

    session = cast(UnitOfWork, tx).session
    scope = {"t": tenant_id, "e": engagement_id, "r": return_id}
    structure_id = cast(
        UUID,
        await session.scalar(
            _INSERT_STRUCTURE,
            {
                **scope,
                "v": version_no,
                "status": status,
                "kind": draft.kind,
                "method": draft.method,
                "convention": draft.convention,
                "income": draft.income if found is None else found.total,
                "dist": None if found is None else found.distributable,
                "by": by,
                "proposal": proposal_id,
                "hash": draft.hash(),
                "engine": None if found is None else found.engine_name,
                "engine_version": None if found is None else found.engine_version,
                "inputs": None if found is None else found.inputs_hash,
                "citations": list(draft.citation_ids),
                "supersedes": supersedes,
            },
        ),
    )
    for rung in draft.rungs:
        await session.execute(
            _INSERT_RUNG,
            {
                **scope,
                "s": structure_id,
                "p": rung.priority,
                "rule": rung.rule_type,
                "params": json.dumps(dict(rung.params), sort_keys=True),
            },
        )
    for result in () if found is None else found.results:
        await session.execute(
            _INSERT_RESULT,
            {
                **scope,
                "s": structure_id,
                "partner": result.partner_id,
                "period": result.period_key,
                "rung": result.rung_priority,
                "amount": result.amount,
            },
        )
    return structure_id


async def save_draft(
    ctx: AuthContext,
    *,
    return_id: UUID,
    engagement_id: UUID,
    year: int,
    expected_version: int,
    draft: Draft,
) -> UUID:
    """A person's new version, Pending approval (the route authorised `allocation_structure.edit`
    on the return). Its results are stored with it, computed by code."""
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    if role not in EDITOR_ROLES:
        raise StructureEditorRequired(facts={"role": role or "none"})
    found = await computed_for(ctx.tenant, return_id, year, draft)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_LOCK, {"k": f"{TARGET}:{return_id}"})
        newest = (await tx.session.execute(_STRUCTURES, {"r": return_id})).mappings().first()
        current = 0 if newest is None else int(newest["version_no"])
        if expected_version != current:
            raise StructureVersionConflict(facts={"current_version": current})
        structure_id = await _insert_version(
            tx, ctx.tenant_id, engagement_id, return_id, current + 1, "pending_approval", draft,
            found, by="human", supersedes=None if newest is None else newest["id"],
        )  # fmt: skip
        tx.record(
            "allocation_structure.drafted",
            target=Target(TARGET, structure_id),
            after=Ref(version_no=current + 1, kind=draft.kind, content_hash=draft.hash()),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    return structure_id


@dataclass(frozen=True)
class Approved:
    sign_off_id: UUID
    structure_id: UUID
    run_id: UUID | None
    run_no: int | None


async def approve(
    ctx: AuthContext,
    *,
    return_id: UUID,
    engagement_id: UUID,
    seen_hash: str,
    statement_version: str,
) -> Approved:
    """Samuel's L3: P-04's sign-off (its rules refuse an agent, staff and the preparer), then the
    person's own `approved` version row and the capital and K-1 re-run."""
    from abacus.modules.agents.api import PlanRequest, start_engagement_run, work_item_runs
    from abacus.modules.review.api import sign_target
    from abacus.modules.tax.entity_run_plan import PROVIDER

    found = await versions(ctx.tenant, return_id)
    if not found or found[0].status != "pending_approval":
        raise StructureNotPending(facts={"return_id": str(return_id)})
    pending = found[0]
    signed = await sign_target(ctx, TARGET, pending.id, 3, seen_hash, statement_version)
    draft = await _draft_of(ctx.tenant, pending)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(_LOCK, {"k": f"{TARGET}:{return_id}"})
        newest = (await tx.session.execute(_STRUCTURES, {"r": return_id})).mappings().first()
        if newest is None or newest["id"] != pending.id:
            raise StructureVersionConflict(facts={"current_version": int(newest["version_no"])})
        approved_id = await _insert_version(
            tx, ctx.tenant_id, engagement_id, return_id, pending.version_no + 1, "approved",
            draft, None, by=pending.proposed_by_kind, proposal_id=pending.proposal_id,
            supersedes=pending.id,
        )  # fmt: skip
        await _copy_results(tx, ctx.tenant_id, engagement_id, return_id, pending.id, approved_id)
        tx.record(
            "allocation_structure.approved",
            target=Target(TARGET, approved_id),
            after=Ref(sign_off=signed.id, level=3, content_hash=pending.content_hash),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    ref = f"tax_return:{return_id}"
    if any(r.active for r in await work_item_runs(ctx.tenant, ref, 5)):
        return Approved(signed.id, approved_id, None, None)
    started = await start_engagement_run(
        ctx,
        engagement_id,
        work_item_ref=ref,
        provider=PROVIDER,
        request=PlanRequest(return_id, "group", RERUN_GROUPS),
    )
    return Approved(signed.id, approved_id, started.run_id, started.run_number)


_COPY_RESULTS: Final = text(
    "INSERT INTO allocation_results (tenant_id, engagement_id, work_item_id, structure_id, "
    "partner_id, period_key, rung_priority, amount) SELECT tenant_id, engagement_id, "
    "work_item_id, :new, partner_id, period_key, rung_priority, amount FROM allocation_results "
    "WHERE structure_id = :old"
)


async def _copy_results(
    tx: object, tenant_id: UUID, engagement_id: UUID, return_id: UUID, old: UUID, new: UUID
) -> None:
    from abacus.kernel.uow import UnitOfWork

    del tenant_id, engagement_id, return_id  # the rows carry their own scope
    await cast(UnitOfWork, tx).session.execute(_COPY_RESULTS, {"old": old, "new": new})


async def _draft_of(tenant: TenantContext, row: StructureRow) -> Draft:
    async with tenant_session(tenant) as session:
        rungs = (await session.execute(_RUNGS, {"s": row.id})).mappings().all()
    return Draft(
        kind=row.kind,
        method=row.method,
        convention=row.convention,
        income=row.income,
        rungs=tuple(
            DraftRung(int(r["priority"]), str(r["rule_type"]), dict(r["params"] or {}))
            for r in rungs
        ),
        citation_ids=row.citation_ids,
    )


# --- the agreement reader's proposal, adopted ----------------------------------------------------


def draft_from_proposal(rows: Sequence[tuple[str, object, Sequence[UUID]]]) -> Draft:
    """The approved proposal's rows (`structure:<parameter>`, its value, its citations) as a draft.
    Rungs and transfers arrive as JSON lists; a value outside the allowed sets is refused."""
    import json

    values: dict[str, object] = {}
    citations: list[UUID] = []
    for key, value, cited in rows:
        if key.startswith("structure:") and key != "structure:convention_question":
            values[key.removeprefix("structure:")] = value
        citations.extend(c for c in cited if c not in citations)
    kind = str(values.get("kind") or "straight_percentage")
    method = str(values.get("method") or "interim_closing")
    convention = str(values.get("convention") or "calendar_day")
    if kind not in ("straight_percentage", "targeted_waterfall"):
        raise StructureInvalid(facts={"code": "unknown_kind"})
    if method not in ("interim_closing", "proration") or convention not in (
        "calendar_day", "semi_monthly", "monthly"
    ):  # fmt: skip
        raise StructureInvalid(facts={"code": "unknown_method_or_convention"})
    rungs: list[DraftRung] = []
    raw = values.get("rungs")
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except ValueError:
            raise StructureInvalid(facts={"code": "rungs_invalid"}) from None
        for n, item in enumerate(cast(list[dict[str, str]], parsed), start=1):
            rule = str(item.get("rule_type", ""))
            if rule not in RULE_TYPES:
                raise StructureInvalid(facts={"code": "unknown_rule_type"})
            params = {k: str(v) for k, v in item.items() if k in ("rate", "target", "gp", "share")}
            rungs.append(DraftRung(int(item.get("priority", n)), rule, params))
    if kind == "straight_percentage" and not rungs:
        rungs.append(DraftRung(1, "straight_pct"))
    return Draft(
        kind=cast(Kind, kind),
        method=cast(Method, method),
        convention=cast(Convention, convention),
        rungs=tuple(rungs),
        citation_ids=tuple(citations),
    )


async def adopt_proposal(tenant: TenantContext, proposal_id: UUID) -> None:
    """The proposal adapter (`allocation_structure`): a person approved the agreement reader's
    proposal, so its structure becomes a version Pending approval (never approved here; the L3
    is a manager's). Runs after the decision commits; an unapproved proposal writes nothing."""
    from abacus.modules.agents.api import approved_proposal_rows, proposal_approver
    from abacus.modules.engagements.api import work_item_engagement

    async with tenant_session(tenant) as session:
        found = await approved_proposal_rows(session, proposal_id)
        approver = await proposal_approver(session, proposal_id)
    if found is None or approver is None:
        return
    _, rows = found
    targets = {r.field_ref.get("target_id") for r in rows}
    if len(targets) != 1 or None in targets:
        return  # one return per proposal (the tool's own rule); anything else is not adopted
    return_id = UUID(str(next(iter(targets))))
    engagement_id = await work_item_engagement(tenant, return_id)
    if engagement_id is None:
        return
    parsed = [
        (
            str(r.field_ref.get("field_key", "")),
            (r.after or {}).get("v") if isinstance(r.after, dict) else None,
            tuple(r.citation_ids or ()),
        )
        for r in rows
    ]
    draft = draft_from_proposal(parsed)
    system = TenantContext(tenant.tenant_id, "system", f"proposal:{proposal_id}", approver)
    async with uow(system) as tx:
        await tx.session.execute(_LOCK, {"k": f"{TARGET}:{return_id}"})
        newest = (await tx.session.execute(_STRUCTURES, {"r": return_id})).mappings().first()
        if newest is not None and newest["proposal_id"] == proposal_id:
            return  # adopted already (the subscriber may run twice)
        current = 0 if newest is None else int(newest["version_no"])
        structure_id = await _insert_version(
            tx, tenant.tenant_id, engagement_id, return_id, current + 1, "pending_approval",
            draft, None, by="agent", proposal_id=proposal_id,
            supersedes=None if newest is None else newest["id"],
        )  # fmt: skip
        tx.record(
            "allocation_structure.proposed",
            target=Target(TARGET, structure_id),
            after=Ref(version_no=current + 1, proposal=proposal_id, adopted_by=approver),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )


# --- the reviewable (P-04) -----------------------------------------------------------------------


def preparer_of(row: StructureRow, approver: UUID | None) -> frozenset[UUID]:
    """Who prepared a version (R-SO-3): the person who saved it, or who adopted the proposal."""
    if row.proposed_by_kind == "agent":
        return frozenset() if approver is None else frozenset({approver})
    try:
        return frozenset({UUID(row.actor_id)})
    except ValueError:
        return frozenset()


async def reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_RETURNS_OF, {"e": engagement_id})).mappings().all()
    out: list[Reviewable] = []
    for r in rows:
        target = (
            r["supersedes_id"] if r["status"] == "approved" and r["supersedes_id"] else r["id"]
        )
        out.append(
            Reviewable(
                TARGET,
                target,
                f"allocation:{r['work_item_id']}",
                f"Allocation structure · Version {r['version_no']}",
                str(r["content_hash"]),
                True,
            )
        )
    return out


async def facts(tenant: TenantContext, structure_id: UUID) -> ReviewableFacts | None:
    from abacus.modules.agents.api import proposal_approver

    async with tenant_session(tenant) as session:
        found = (await session.execute(_STRUCTURE, {"i": structure_id})).mappings().first()
        if found is None:
            return None
        row = _row(found)
        approver = (
            None if row.proposal_id is None else await proposal_approver(session, row.proposal_id)
        )
    return ReviewableFacts(
        target_type=TARGET,
        target_id=row.id,
        engagement_id=row.engagement_id,
        content_hash=row.content_hash,
        version_no=row.version_no,
        preparer_user_ids=preparer_of(row, approver),
        required_levels=(1, 3),
        label=f"Allocation structure · Version {row.version_no}",
        context_label="Allocation Structure",
        work_item_id=row.work_item_id,
        citation_count=len(row.citation_ids),
        cited_count=len(row.citation_ids),
        requirement_key=TARGET,
    )


def register() -> None:
    """At the tax api's import: the reviewable, its facts and the proposal adapter."""
    from abacus.modules.agents.api import register_proposal_adapter

    register_reviewable(TARGET, reviewables)
    register_reviewable_facts(TARGET, facts)
    register_proposal_adapter(TARGET, adopt_proposal)


__all__ = [
    "EDITOR_ROLES",
    "RERUN_GROUPS",
    "TARGET",
    "Approved",
    "Computed",
    "Draft",
    "DraftRung",
    "PartnerFacts",
    "PeriodFacts",
    "StructureEditorRequired",
    "StructureInvalid",
    "StructureNotPending",
    "StructureVersionConflict",
    "StructureView",
    "approve",
    "compute",
    "draft_from_proposal",
    "preparer_of",
    "preview",
    "register",
    "rung_params",
    "save_draft",
    "view",
]
