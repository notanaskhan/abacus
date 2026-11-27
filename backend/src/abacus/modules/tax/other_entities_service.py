"""Other-entity workpapers (T-06-T42; TASK-8911; SPEC-702 F5, AC-22 to AC-26; TXP-13; amber).

The 1120-S AAA, the 1120 ASC 740 provision and the 990 Part IX, read from the return's rows
(0966) and computed by code (E10, E11, E12; ADR-050). A Filed or Accepted return is read-only:
every write answers 409 `return_locked`.

- **AAA** (TXP-13 a): the Schedule M-2 columns rolled by E10 (`aaa_roll` for the AAA column, the
  same line arithmetic for PTI, E&P and OAA) and the shareholders' percentages.
- **Provision** (TXP-13 b, b2): current + deferred = total, the ETR and the rate
  reconciliation's tally; an off reconciliation reports its unclassified amount. "Explain…" on an
  unclassified item creates an SHL-15 issue (a person's act); the classification is a reviewer's,
  and the agent's suggestion for it arrives with T-06-T54 (zero gateway calls here).
- **Part IX** (TXP-13 c, c2): E12 foots and crossfoots every line; program ratio and public
  support by code.
- **Time-study allocation** (TXP-13 c3): a person starts it; code reads each time-study line's
  percentages (the imported time-study table on the line; the agent's extraction with citations
  is T-06-T54's), E12 allocates them, and the result lands as a `time_study_allocation` proposal
  on a `tax.return_analyst` run. Nothing changes until a person adopts it: the adapter writes the
  lines then (INV-1).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import Row, text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.tax.compute import exempt as e12
from abacus.modules.tax.compute import s_corp as e10
from abacus.modules.tax.entity_depth_errors import ReturnLocked

READ: Final = "other_workpapers.read"
EXPLAIN: Final = "issue.create"
ALLOCATE: Final = "allocation_run.start"
LOCKED: Final = frozenset({"filed", "accepted"})
ZERO: Final = Decimal(0)
HUNDRED: Final = Decimal(100)
PROPOSAL_KIND: Final = "time_study_allocation"
LINE_TARGET: Final = "functional_expense_line"
CAPABILITY: Final = "tax.return_analyst"
COLUMNS: Final = e12.COLUMNS


class TimeStudyMissing(DomainConflict):
    """No line on the return is allocated by a time study with its percentages imported."""

    code = "time_study_missing"


class NotUnclassified(DomainConflict):
    """Only an unclassified reconciliation difference is explained."""

    code = "not_unclassified"


@dataclass(frozen=True)
class _Return:
    return_id: UUID
    engagement_id: UUID
    status: str
    resource: Resource


async def _loaded(ctx: AuthContext, return_id: UUID, action: str) -> _Return:
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    resource = await return_resource(ctx, loaded)
    await authorise(ctx, action, resource)
    async with tenant_session(ctx.tenant) as session:
        status = await session.scalar(
            text("SELECT status FROM tax_returns WHERE work_item_id = :r"), {"r": return_id}
        )
    return _Return(return_id, loaded.facts.engagement_id, str(status), resource)


def _writable(found: _Return) -> None:
    if found.status in LOCKED:
        raise ReturnLocked(facts={"work_item_id": str(found.return_id)})


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


# --- AAA (E10) -----------------------------------------------------------------------------------


@dataclass(frozen=True)
class AaaLine:
    line_no: int
    aaa: Decimal
    pti: Decimal
    e_and_p: Decimal
    oaa: Decimal


@dataclass(frozen=True)
class Shareholder:
    name: str
    pct: Decimal
    ordinary_income: Decimal
    interest: Decimal
    nondeductible: Decimal
    distributions: Decimal


@dataclass(frozen=True)
class Aaa:
    aaa: Decimal
    pti: Decimal
    e_and_p: Decimal
    oaa: Decimal
    shareholder_pcts: tuple[Decimal, ...]
    locked: bool
    # T-06-T52 (DEC-6036): the lines and the allocation as stored (TXP-13 a).
    lines: tuple[AaaLine, ...] = ()
    shareholders: tuple[Shareholder, ...] = ()


def column_ending(lines: Mapping[int, Decimal]) -> Decimal:
    """Schedule M-2's line arithmetic: 1 + 2 + 3 - 4 - 5 - 7 (line 6 is the subtotal, 8 the
    ending)."""
    g = lines.get
    return g(1, ZERO) + g(2, ZERO) + g(3, ZERO) - g(4, ZERO) - g(5, ZERO) - g(7, ZERO)


def aaa_ending(lines: Mapping[int, Decimal]) -> Decimal:
    """E10's AAA roll: a distribution beyond the balance before it is not taken from AAA."""
    g = lines.get
    return e10.aaa_roll(
        g(1, ZERO),
        income=g(2, ZERO) + g(3, ZERO),
        losses=g(4, ZERO),
        nondeductible=g(5, ZERO),
        distributions=g(7, ZERO),
    ).ending


_AAA: Final = text(
    "SELECT line_no, col_aaa, col_pti, col_e_and_p, col_oaa FROM aaa_lines "
    "WHERE work_item_id = :r ORDER BY line_no"
)
_HOLDERS: Final = text(
    "SELECT partner_id, pct, ordinary_income, interest, nondeductible, distributions "
    "FROM shareholder_allocations WHERE work_item_id = :r ORDER BY pct DESC, partner_id"
)


async def aaa(ctx: AuthContext, return_id: UUID) -> Aaa:
    found = await _loaded(ctx, return_id, READ)
    from abacus.modules.tax.entity_schedules import recipients

    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_AAA, {"r": return_id})).all()
        holders = (await session.execute(_HOLDERS, {"r": return_id})).all()
    if not rows:
        raise NotFound("aaa_lines")
    pcts = tuple(Decimal(h.pct) for h in holders)
    names = dict(await recipients(ctx.tenant, return_id)) if holders else {}
    cols = {c: {int(r.line_no): Decimal(getattr(r, c)) for r in rows}
            for c in ("col_aaa", "col_pti", "col_e_and_p", "col_oaa")}  # fmt: skip
    return Aaa(
        aaa_ending(cols["col_aaa"]),
        column_ending(cols["col_pti"]),
        column_ending(cols["col_e_and_p"]),
        column_ending(cols["col_oaa"]),
        pcts,
        found.status in LOCKED,
        tuple(
            AaaLine(int(r.line_no), Decimal(r.col_aaa), Decimal(r.col_pti),
                    Decimal(r.col_e_and_p), Decimal(r.col_oaa))
            for r in rows
        ),
        tuple(
            Shareholder(names.get(h.partner_id, ""), Decimal(h.pct), Decimal(h.ordinary_income),
                        Decimal(h.interest), Decimal(h.nondeductible), Decimal(h.distributions))
            for h in holders
        ),
    )  # fmt: skip


# --- provision (E11) -----------------------------------------------------------------------------

ProvisionView = Literal["provision", "rate_reconciliation", "deferred"]


@dataclass(frozen=True)
class ReconItem:
    item_id: UUID
    description: str
    amount: Decimal
    rate_effect: Decimal | None
    classification: str


@dataclass(frozen=True)
class DeferredItem:
    kind: str
    label: str
    temporary_difference: Decimal
    rate: Decimal
    amount: Decimal


@dataclass(frozen=True)
class Provision:
    view: ProvisionView
    current: Decimal
    deferred: Decimal
    total: Decimal
    effective_rate: Decimal
    tally: Literal["tie", "off"]
    unclassified: Decimal | None
    # T-06-T52 (DEC-6036): the computation, reconciliation and deferred inventory as stored.
    pretax_book_income: Decimal | None = None
    permanent_total: Decimal | None = None
    temporary_total: Decimal | None = None
    taxable_income: Decimal | None = None
    blended_rate: Decimal | None = None
    recon_items: tuple[ReconItem, ...] = ()
    deferred_items: tuple[DeferredItem, ...] = ()


_PROVISION: Final = text(
    "SELECT id, current_tax, deferred_tax, total_provision, etr, recon_status, off_amount, "
    "pretax_book_income, permanent_total, temporary_total, taxable_income, blended_rate "
    "FROM tax_provisions WHERE work_item_id = :r"
)
_RECON: Final = text(
    "SELECT id, description, amount, rate_effect, classification FROM rate_recon_items "
    "WHERE provision_id = :p ORDER BY classification = 'unclassified', item_key"
)
_DEFERRED: Final = text(
    "SELECT kind, label, temporary_difference, rate, amount FROM deferred_tax_items "
    "WHERE provision_id = :p ORDER BY kind DESC, label"
)
_UNCLASSIFIED: Final = text(
    "SELECT coalesce(sum(amount), 0) FROM rate_recon_items WHERE provision_id = :p "
    "AND classification = 'unclassified'"
)


async def provision(ctx: AuthContext, return_id: UUID, view: ProvisionView) -> Provision:
    await _loaded(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_PROVISION, {"r": return_id})).first()
        unclassified = None if row is None else await session.scalar(_UNCLASSIFIED, {"p": row.id})
        recon: Sequence[Row[Any]] = ()  # Any: SQL rows of mixed column types
        dtx: Sequence[Row[Any]] = ()  # Any: as above
        if row is not None:
            recon = (await session.execute(_RECON, {"p": row.id})).all()
            dtx = (await session.execute(_DEFERRED, {"p": row.id})).all()
    if row is None:
        raise NotFound("tax_provision")
    current, deferred = Decimal(row.current_tax), Decimal(row.deferred_tax)
    total = current + deferred  # E11: the provision is current plus deferred (the CHECK holds)
    off = str(row.recon_status) == "off"
    open_amount = Decimal(row.off_amount) if off else None
    if open_amount is None and unclassified:
        open_amount = Decimal(unclassified)
    return Provision(
        view, current, deferred, total,
        Decimal(row.etr) if row.etr is not None else ZERO,
        "off" if off or open_amount else "tie",
        open_amount,
        Decimal(row.pretax_book_income), Decimal(row.permanent_total),
        Decimal(row.temporary_total), Decimal(row.taxable_income), Decimal(row.blended_rate),
        tuple(ReconItem(r.id, str(r.description), Decimal(r.amount),
                        None if r.rate_effect is None else Decimal(r.rate_effect),
                        str(r.classification)) for r in recon),
        tuple(DeferredItem(str(d.kind), str(d.label), Decimal(d.temporary_difference),
                           Decimal(d.rate), Decimal(d.amount)) for d in dtx),
    )  # fmt: skip


_ITEM: Final = text(
    "SELECT i.id, i.item_key, i.classification FROM rate_recon_items i "
    "JOIN tax_provisions p ON p.id = i.provision_id WHERE i.id = :i AND p.work_item_id = :r"
)


async def explain_item(ctx: AuthContext, return_id: UUID, item_id: UUID) -> UUID:
    """ "Explain…" on an unclassified reconciliation difference: an SHL-15 issue on the return
    (a person's act; the reviewer classifies). Answers the issue's id."""
    from abacus.modules.review.api import create_issue

    _human(ctx, EXPLAIN)
    found = await _loaded(ctx, return_id, EXPLAIN)
    _writable(found)
    async with tenant_session(ctx.tenant) as session:
        item = (await session.execute(_ITEM, {"i": item_id, "r": return_id})).first()
    if item is None:
        raise NotFound("rate_recon_item")
    if str(item.classification) != "unclassified":
        raise NotUnclassified(facts={"item_id": str(item_id)})
    return await create_issue(
        ctx, record_type="tax_return", record_id=return_id, kind="review_point",
        priority="medium", title="Classify the unclassified rate reconciliation difference",
        internal_note=None, client_wording=None, client_contact_id=None, assignee_user_id=None,
        assignee_agent=False, blocks=(), source_ref=f"provision_item:{item_id}",
        work_item_id=return_id,
    )  # fmt: skip


# --- Part IX and public support (E12) ------------------------------------------------------------

ExpenseView = Literal["part_ix", "allocation_basis"]


@dataclass(frozen=True)
class ExpenseRow:
    line: str
    label: str
    total: Decimal
    program: Decimal
    management: Decimal
    fundraising: Decimal
    basis: str
    time_study: Mapping[str, Decimal] | None
    memo_evidence_version_id: UUID | None


@dataclass(frozen=True)
class FunctionalExpenses:
    view: ExpenseView
    part_ix: e12.PartIX
    public_support: Decimal
    # T-06-T52 (DEC-6036): Part IX's lines as stored (each crossfoots by CHECK).
    lines: tuple[ExpenseRow, ...] = ()


_LINES: Final = text(
    "SELECT id, part_ix_line, label, total, program, management_general, fundraising, "
    "allocation_basis, time_study, source_memo_evidence_version_id FROM functional_expense_lines "
    "WHERE work_item_id = :r ORDER BY part_ix_line"
)
_SUPPORT: Final = text(
    "SELECT public_support, total_support FROM public_support_tests WHERE work_item_id = :r "
    "ORDER BY upper(years) DESC LIMIT 1"
)


def _line(r: Row[Any]) -> e12.ExpenseLine:  # Any: a SQL row of mixed column types
    basis: Literal["direct", "time_study"] = (
        "time_study" if r.allocation_basis == "time_study" else "direct"
    )
    return e12.ExpenseLine(
        str(r.part_ix_line), str(r.label), Decimal(r.total), Decimal(r.program),
        Decimal(r.management_general), Decimal(r.fundraising), basis,
    )  # fmt: skip


async def functional_expenses(
    ctx: AuthContext, return_id: UUID, view: ExpenseView
) -> FunctionalExpenses:
    await _loaded(ctx, return_id, READ)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_LINES, {"r": return_id})).all()
        support = (await session.execute(_SUPPORT, {"r": return_id})).first()
    if not rows:
        raise NotFound("functional_expense_lines")
    computed = e12.part_ix([_line(r) for r in rows])
    pct = (
        ZERO
        if support is None
        else e12.public_support(
            Decimal(support.public_support), Decimal(support.total_support)
        ).pct
    )

    def study(raw: object) -> Mapping[str, Decimal] | None:
        if not isinstance(raw, dict):
            return None
        stored = cast("dict[str, object]", raw)
        pairs: object = stored.get("pct", stored)
        if not isinstance(pairs, dict):
            return None
        return {str(k): Decimal(str(v)) for k, v in cast("dict[str, object]", pairs).items()}

    lines = tuple(
        ExpenseRow(str(r.part_ix_line), str(r.label), Decimal(r.total), Decimal(r.program),
                   Decimal(r.management_general), Decimal(r.fundraising),
                   str(r.allocation_basis), study(r.time_study),
                   r.source_memo_evidence_version_id)
        for r in rows
    )  # fmt: skip
    return FunctionalExpenses(view, computed, pct, lines)


# --- the time-study allocation (TXP-13 c3) -------------------------------------------------------


def allocate(rows: Sequence[Any]) -> list[tuple[UUID, e12.ExpenseLine]]:  # Any: row values
    """E12 over every time-study line whose percentages were imported (`time_study.pct`); others
    are left out. Percentages that do not sum to 100 raise `ValueError` (E12)."""
    out: list[tuple[UUID, e12.ExpenseLine]] = []
    for r in rows:
        study = r.time_study
        if r.allocation_basis != "time_study" or not isinstance(study, dict):
            continue
        raw = cast("dict[str, object]", study).get("pct")
        if not isinstance(raw, dict):
            continue
        given = cast("dict[str, object]", raw)
        pct: dict[e12.Column, Decimal] = {c: Decimal(str(given.get(c, "0"))) for c in e12.COLUMNS}
        line = e12.time_study(str(r.part_ix_line), str(r.label), Decimal(r.total), pct)
        out.append((UUID(str(r.id)), line))
    return out


@dataclass(frozen=True)
class AllocationRun:
    run_id: UUID
    proposal_id: UUID


async def start_allocation(ctx: AuthContext, return_id: UUID) -> AllocationRun:
    """A person starts the time-study allocation; the result is a proposal (module docstring)."""
    from abacus.modules.agents.api import (
        ProposedRow,
        create_proposal,
        end_capability_run,
        start_capability_run,
    )

    _human(ctx, ALLOCATE)
    found = await _loaded(ctx, return_id, ALLOCATE)
    _writable(found)
    async with tenant_session(ctx.tenant) as session:
        rows = list((await session.execute(_LINES, {"r": return_id})).all())
    try:
        allocated = allocate(rows)
    except ValueError:
        raise TimeStudyMissing(facts={"reason": "percentages_do_not_sum"}) from None
    if not allocated:
        raise TimeStudyMissing(facts={"work_item_id": str(return_id)})
    agent = await start_capability_run(ctx, CAPABILITY, found.engagement_id)
    if agent is None:
        raise TimeStudyMissing(facts={"reason": "run_not_recorded"})
    by_id = {UUID(str(r.id)): r for r in rows}
    proposed = [
        ProposedRow(
            target_type=LINE_TARGET, target_id=line_id, field_key="allocation",
            label=f"Part IX line {line.line}",
            before={"t": "json", "v": {c: str(getattr(by_id[line_id], c)) for c in COLUMNS}},
            after={"t": "json", "v": {"program": str(line.program),
                                      "management_general": str(line.management_general),
                                      "fundraising": str(line.fundraising)}},
            cause="time_study",
        )
        for line_id, line in allocated
    ]  # fmt: skip
    proposal = await create_proposal(
        agent, engagement_id=found.engagement_id, kind=PROPOSAL_KIND,
        title="Time-study allocation of Part IX", rows=proposed,
    )  # fmt: skip
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO allocation_runs (tenant_id, engagement_id, work_item_id, run_id, "
                "status, proposal_id) VALUES (:t, :e, :r, :run, 'proposed', :p)"
            ),
            {"t": ctx.tenant_id, "e": found.engagement_id, "r": return_id,
             "run": agent.agent_run_id, "p": proposal},
        )  # fmt: skip
        tx.record(
            "allocation_run.proposed",
            target=Target("tax_return", return_id),
            after=Ref(run=agent.agent_run_id, proposal=proposal, lines=len(proposed)),
            scope=Scope(engagement_id=found.engagement_id, work_item_id=return_id),
        )
    await end_capability_run(agent, status="succeeded", output={"lines": len(proposed)})
    return AllocationRun(agent.agent_run_id, proposal)


async def adopt_allocation(tenant: TenantContext, proposal_id: UUID) -> None:
    """The proposal adapter: a person approved the allocation, so each line takes its split (the
    crossfoot CHECK holds) as the approver; an unapproved proposal writes nothing."""
    from abacus.modules.agents.api import approved_proposal_rows, proposal_approver

    async with tenant_session(tenant) as session:
        found = await approved_proposal_rows(session, proposal_id)
        approver = await proposal_approver(session, proposal_id)
    if found is None or approver is None:
        return
    _, rows = found
    system = TenantContext(tenant.tenant_id, "system", f"proposal:{proposal_id}", approver)
    async with uow(system) as tx:
        for r in rows:
            value = (r.after or {}).get("v") if isinstance(r.after, dict) else None
            target = r.field_ref.get("target_id")
            if not isinstance(value, dict) or target is None:
                continue
            split = cast("dict[str, str]", value)
            await tx.session.execute(
                text(
                    "UPDATE functional_expense_lines SET program = :pg, management_general = :mg, "
                    "fundraising = :fr, allocation_basis = 'time_study' WHERE id = :i"
                ),
                {"pg": Decimal(split["program"]), "mg": Decimal(split["management_general"]),
                 "fr": Decimal(split["fundraising"]), "i": UUID(str(target))},
            )  # fmt: skip
        await tx.session.execute(
            text("UPDATE allocation_runs SET status = 'approved' WHERE proposal_id = :p"),
            {"p": proposal_id},
        )
        tx.record("allocation_run.adopted", target=Target("proposal", proposal_id))


def register() -> None:
    from abacus.modules.agents.api import register_proposal_adapter, register_suggestion_target

    register_suggestion_target(LINE_TARGET, engagement_of=line_engagement)
    register_proposal_adapter(PROPOSAL_KIND, adopt_allocation)


async def line_engagement(tenant: TenantContext, line_id: UUID) -> UUID | None:
    async with tenant_session(tenant) as session:
        return cast(
            UUID | None,
            await session.scalar(
                text("SELECT engagement_id FROM functional_expense_lines WHERE id = :i"),
                {"i": line_id},
            ),
        )


__all__ = [
    "Aaa",
    "AllocationRun",
    "FunctionalExpenses",
    "NotUnclassified",
    "Provision",
    "TimeStudyMissing",
    "aaa",
    "aaa_ending",
    "adopt_allocation",
    "allocate",
    "column_ending",
    "explain_item",
    "functional_expenses",
    "provision",
    "register",
    "start_allocation",
]
