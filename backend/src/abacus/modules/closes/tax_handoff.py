"""The close-to-tax hand-off, closes side (C-02-T39; TASK-8920; C-02 F8; CLS-12 a to d; C12;
ADR-004; DEC-5922; amber).

- **Availability.** Only a December close, and only once Locked: any other month or state answers
  `not_available` with "Available after the December <year> close locks" (CLS-12 b), and the
  publish refuses 409 `handoff_not_available` (C12's `close_lock` gate says the same). A close
  with no original return for the entity and year is not available either.
- **Preview** (CLS-12 a): the source (period, locked date, `TB v<n>`, the trial balance's tie),
  the target (the return, its engine and tax team: `tax.api.handoff_target`), the five schedules
  computed by code from the close's arrangements and the year's TB (the fixed asset register,
  prepaid insurance, deferred revenue, shareholder distributions, accrued payroll), each on by
  default, and the close's tax-relevant items (its CLS-06 notes, open or resolved) with "Create
  tax issue" on. `version` is the close's row version: the publish names the one the person saw.
- **Publish** (`tax_handoff.publish`, a manager or partner, a live person): C12 `tb_handoff.create`
  lands the year's TB snapshot as the return's UTB with its provenance (`close_lock`, the
  accounts with last year's tax-line codes where the prior year-end TB carried them, else blank
  for the tax team), the toggled schedules with their figures and the toggled items as
  `close_issue` tax items (the tax landing raises them on the TXP-10 route). Then one insert-only
  `tax_handoffs` row (`TB v<n>`), superseding the previous one when the close was reopened and
  locked again (the table's trigger sets `superseded_by_id`), and `tax_handoff.published` (and
  `tax_handoff.superseded`) to the return's preparer and reviewer.
- **TJEs never post**: the hand-off carries the TB only; tax-only entries stay in the tax
  workpapers (TJE-001 holds on the posting side).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, ClassVar, Final, Literal, cast
from uuid import UUID

from pydantic import Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import DomainEvent, Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, authorise

READ: Final = "tax_handoff.read"
PUBLISH: Final = "tax_handoff.publish"
ZERO: Final = Decimal(0)
Status = Literal["not_available", "ready", "handed_off", "superseded"]
_I = classified("internal")

# CLS-12's schedules, in the sheet's order, with their C12 kinds.
SCHEDULES: Final[tuple[tuple[str, str], ...]] = (
    ("fixed_assets", "Fixed asset register"),
    ("prepaid_expenses", "Prepaid insurance"),
    ("deferred_revenue", "Deferred revenue"),
    ("shareholder_distributions", "Shareholder distributions"),
    ("accrued_liabilities", "Accrued payroll at Dec 31"),
)


class HandoffNotAvailable(DomainConflict):
    """Not a Locked December close, or no return to land on (CLS-12 b)."""

    code = "handoff_not_available"


class HandoffStale(DomainConflict):
    """The close changed since the person read the sheet (its row version)."""

    code = "handoff_preview_changed"


class TaxHandoffPublished(DomainEvent):
    """A December close's TB landed on a return (identifiers only; DEC-60)."""

    event_type: ClassVar[str] = "tax_handoff.published"

    tax_handoff_id: Annotated[UUID, _I]
    close_id: Annotated[UUID, _I]
    tax_return_id: Annotated[UUID, _I]
    by_user: Annotated[UUID, _I]
    recipient_user_ids: Annotated[list[UUID], _I] = Field(default_factory=list[UUID])


class TaxHandoffSuperseded(DomainEvent):
    event_type: ClassVar[str] = "tax_handoff.superseded"

    tax_handoff_id: Annotated[UUID, _I]
    close_id: Annotated[UUID, _I]
    tax_return_id: Annotated[UUID, _I]
    by_user: Annotated[UUID, _I]
    recipient_user_ids: Annotated[list[UUID], _I] = Field(default_factory=list[UUID])


@dataclass(frozen=True)
class Schedule:
    key: str
    label: str
    included: bool
    figures: Mapping[str, Decimal]


@dataclass(frozen=True)
class Item:
    issue_id: UUID
    title: str
    resolved: bool


@dataclass(frozen=True)
class Availability:
    status: Status
    reason: str | None
    tb_version: str | None
    locked_at: date | None
    target_return_id: UUID | None
    schedules: tuple[Schedule, ...]
    items: tuple[Item, ...]
    superseded_on_next: bool
    version: int
    balanced: bool | None = None
    # C-02-T48 (CLS-12 Target): the return's form, year, engine and tax team; and the latest
    # hand-off's person and time (c2's provenance banner).
    target: Any = None  # Any: tax.api.HandoffTarget (closes imports it lazily, never at load)
    handed_off_by: UUID | None = None
    handed_off_at: datetime | None = None
    reopened_at: datetime | None = None  # CLS-12 d: "reopened on Jan 20"


# --- pure ----------------------------------------------------------------------------------------


def month_words(period: str) -> str:
    year, month = period.split("-")
    return f"{date(int(year), int(month), 1):%B} {year}"


def gate(period: str, status: str) -> str | None:
    """Why the close can't hand off yet (None: it can)."""
    year, month = period.split("-")
    if month != "12" or status != "locked":
        return f"Available after the December {year} close locks"
    return None


@dataclass(frozen=True)
class ScheduleResult:
    """One arrangement's results over the year: (period, aje, ending balance)."""

    kind: str  # prepaid | fixed_asset | accrual | deferred_revenue
    scheduled_total: Decimal
    periods: Sequence[tuple[str, Decimal, Decimal]]


def schedules(
    year: int,
    results: Sequence[ScheduleResult],
    distributions: Decimal | None,
) -> tuple[Schedule, ...]:
    """The five schedules' figures (code; ADR-050): each arrangement kind summed over the year's
    closes, its December ending balance; distributions from the TB."""
    december = f"{year}-12"

    def year_total(r: ScheduleResult) -> Decimal:
        return sum((abs(a) for p, a, _e in r.periods if p.startswith(f"{year}-")), ZERO)

    def ending(r: ScheduleResult) -> Decimal:
        return next((e for p, _a, e in r.periods if p == december), ZERO)

    def of(kind: str) -> list[ScheduleResult]:
        return [r for r in results if r.kind == kind]

    assets = of("fixed_asset")
    cost = sum((r.scheduled_total for r in assets), ZERO)
    figures: dict[str, dict[str, Decimal]] = {
        "fixed_assets": {
            "cost": cost,
            "accumulated_depreciation": cost - sum((ending(r) for r in assets), ZERO),
            "book_depreciation": sum((year_total(r) for r in assets), ZERO),
        },
        "prepaid_expenses": {
            "amortized": sum((year_total(r) for r in of("prepaid")), ZERO),
            "ending_balance": sum((ending(r) for r in of("prepaid")), ZERO),
        },
        "deferred_revenue": {
            "recognized": sum((year_total(r) for r in of("deferred_revenue")), ZERO),
            "ending_balance": sum((ending(r) for r in of("deferred_revenue")), ZERO),
        },
        "shareholder_distributions": {"total": abs(distributions or ZERO)},
        "accrued_liabilities": {
            "ending_balance": sum((ending(r) for r in of("accrual")), ZERO),
        },
    }
    present = {
        "fixed_assets": bool(assets), "prepaid_expenses": bool(of("prepaid")),
        "deferred_revenue": bool(of("deferred_revenue")),
        "shareholder_distributions": distributions is not None,
        "accrued_liabilities": bool(of("accrual")),
    }  # fmt: skip
    return tuple(
        Schedule(key, label, True, figures[key]) for key, label in SCHEDULES if present[key]
    )


def tb_version(prior_count: int) -> str:
    return f"TB v{prior_count + 1}"


# --- reads ---------------------------------------------------------------------------------------

_HANDOFFS: Final = text(
    "SELECT id, version_no, handed_off_at, superseded_by_id, target_tax_return_id, handed_off_by "
    "FROM tax_handoffs WHERE close_id = :c ORDER BY handed_off_at, id"
)
_REOPENED: Final = text("SELECT max(at) FROM close_reopenings WHERE close_id = :c")
_RESULTS: Final = text(
    "SELECT a.id, a.kind, v.scheduled_total, r.period, r.aje, r.ending_balance "
    "FROM arrangements a JOIN LATERAL (SELECT scheduled_total FROM arrangement_versions x "
    "WHERE x.arrangement_id = a.id ORDER BY x.version DESC LIMIT 1) v ON true "
    "JOIN close_schedule_results r ON r.arrangement_id = a.id "
    "WHERE a.client_entity_id = :e AND r.period LIKE :year ORDER BY a.id, r.period, r.computed_at"
)


async def _schedule_results(
    tenant: TenantContext, entity: UUID, year: int
) -> list[ScheduleResult]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_RESULTS, {"e": entity, "year": f"{year}-%"})).all()
    by: dict[UUID, tuple[str, Decimal, dict[str, tuple[Decimal, Decimal]]]] = {}
    for r in rows:
        kind, total, periods = by.setdefault(
            cast(UUID, r.id), (str(r.kind), Decimal(r.scheduled_total), {})
        )
        periods[str(r.period)] = (Decimal(r.aje), Decimal(r.ending_balance))  # the newest wins
        by[cast(UUID, r.id)] = (kind, total, periods)
    return [
        ScheduleResult(kind, total, tuple((p, a, e) for p, (a, e) in sorted(periods.items())))
        for kind, total, periods in by.values()
    ]


@dataclass(frozen=True)
class YearTb:
    snapshot_id: UUID
    accounts: tuple[tuple[str, str, Decimal], ...]  # (code, name, balance)


async def _year_tb(tenant: TenantContext, entity: UUID, year: int) -> YearTb | None:
    from abacus.modules.ledger.api import year_end_trial_balance

    found = await year_end_trial_balance(tenant, entity, date(year, 1, 1), date(year, 12, 31))
    if found is None:
        return None
    return YearTb(
        found.snapshot_id,
        tuple((a.code, a.name, Decimal(a.closing)) for a in found.accounts),
    )


def distributions_of(accounts: Sequence[tuple[str, str, Decimal]]) -> Decimal | None:
    """The TB's shareholder distribution accounts (an equity account named for distributions),
    summed; None when the TB has none."""
    found = [b for _c, name, b in accounts if "distribution" in name.lower()]
    return sum(found, ZERO) if found else None


async def _items(ctx: AuthContext, close_id: UUID) -> tuple[Item, ...]:
    """The close's CLS-06 notes: its tax-relevant items (open or resolved)."""
    from abacus.modules.closes.issues import CLOSE_TARGET, ISSUE_SUBJECT, NOTE_PATH, OPEN_STATUSES
    from abacus.modules.review.api import list_issues, open_text

    page = await list_issues(
        ctx, record_type=CLOSE_TARGET, record_id=close_id, engagement_id=None, status=None,
        kind=None, limit=1000,
    )  # fmt: skip
    out: list[Item] = []
    for row in page.rows:
        if not (row.category_path or "").startswith(NOTE_PATH):
            continue
        title = await open_text(ctx.tenant, row.title_sealed, ISSUE_SUBJECT, row.id, "title")
        out.append(Item(row.id, title, row.status not in OPEN_STATUSES))
    return tuple(sorted(out, key=lambda i: str(i.issue_id)))


async def availability(ctx: AuthContext, close_id: UUID) -> Availability:
    """CLS-12's sheet (module docstring)."""
    from abacus.modules.closes.service import visible_close
    from abacus.modules.engagements.api import engagement_resource_of
    from abacus.modules.tax.api import handoff_target

    close = await visible_close(ctx, close_id)
    await authorise(ctx, READ, await engagement_resource_of(ctx.tenant, close.engagement_id))
    async with tenant_session(ctx.tenant) as session:
        handoffs = (await session.execute(_HANDOFFS, {"c": close_id})).all()
        reopened = await session.scalar(_REOPENED, {"c": close_id})
    latest = handoffs[-1] if handoffs else None
    version = tb_version(len(handoffs))
    locked = None if close.locked_at is None else close.locked_at.date()
    reason = gate(close.period, close.status)
    year = int(close.period[:4])
    target = (
        None if close.client_entity_id is None
        else await handoff_target(ctx.tenant, close.client_entity_id, year)
    )  # fmt: skip
    if reason is None and target is None:
        reason = f"No {year} return for this entity yet"
    reopened_since = (
        latest is not None and reopened is not None
        and cast(datetime, reopened) > cast(datetime, latest.handed_off_at)
    )  # fmt: skip
    if reason is not None:
        status: Status = "superseded" if reopened_since else "not_available"
        return Availability(
            status, reason, None, locked, None if target is None else target.return_id, (), (),
            reopened_since, close.row_version,
        )  # fmt: skip
    status = "ready" if latest is None or reopened_since else "handed_off"
    shown = version if status == "ready" or latest is None else str(latest.version_no)
    tb = await _year_tb(ctx.tenant, cast(UUID, close.client_entity_id), year)
    found = schedules(
        year,
        await _schedule_results(ctx.tenant, cast(UUID, close.client_entity_id), year),
        None if tb is None else distributions_of(tb.accounts),
    )
    balanced = None if tb is None else sum((b for *_r, b in tb.accounts), ZERO) == ZERO
    return Availability(
        status, None, shown, locked, target.return_id if target else None, found,
        await _items(ctx, close_id), reopened_since, close.row_version, balanced, target,
        None if latest is None else latest.handed_off_by,
        None if latest is None else latest.handed_off_at,
        cast(datetime, reopened) if reopened_since else None,
    )  # fmt: skip


# --- publish -------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Published:
    handoff_id: UUID
    tb_version: str
    tax_issues: int
    c12_ref: UUID


async def book_income(
    tenant: TenantContext,
    engagement_id: UUID,
    year: int,
    accounts: Sequence[tuple[str, str, Decimal]],
) -> Decimal:
    """Book income before tax: the income statement accounts (revenue and expense groupings of
    the year's FS mapping) negated (credits are negative); zero without a mapping."""
    from abacus.modules.ledger.api import engagement_trial_balances, mapping_view

    tbs = [t for t in await engagement_trial_balances(tenant, engagement_id)
           if t.period_end.year == year]  # fmt: skip
    if not tbs:
        return ZERO
    newest = max(tbs, key=lambda t: (t.period_end, t.current_version_no))
    view = await mapping_view(tenant, engagement_id, newest.id)
    if view is None:
        return ZERO
    income_lines = {
        line.id for g in view.groupings if g.class_ in ("revenue", "expenses") for line in g.lines
    }
    codes = {a.account_code for a in view.accounts if a.fs_line_id in income_lines}
    return -sum((b for c, _n, b in accounts if c in codes), ZERO)


async def _prior_codes(tenant: TenantContext, engagement_id: UUID, year: int) -> dict[str, str]:
    """Last year's tax-line codes: the prior year-end TB's tax mapping set, when it has one."""
    from abacus.modules.ledger.api import (
        engagement_trial_balances,
        form_line_rows,
        tax_mapping_set,
    )

    tbs = [t for t in await engagement_trial_balances(tenant, engagement_id)
           if t.period_end.year == year - 1]  # fmt: skip
    if not tbs:
        return {}
    prior = max(tbs, key=lambda t: (t.period_end, t.current_version_no))
    set_id = await tax_mapping_set(tenant, prior.id)
    if set_id is None:
        return {}
    rows = await form_line_rows(tenant, set_id)
    return {code: line for code, line in rows.items() if line}


_INSERT: Final = text(
    "INSERT INTO tax_handoffs (tenant_id, close_id, client_entity_id, version_no, tb_snapshot_id, "
    "target_tax_return_id, engine, schedules, items, c12_ref, handed_off_by, supersedes_id) "
    "VALUES (:t, :c, :e, :v, :snap, :r, :engine, CAST(:s AS jsonb), CAST(:i AS jsonb), :ref, "
    ":by, :sup) RETURNING id"
)


async def publish(
    ctx: AuthContext,
    close_id: UUID,
    *,
    schedules_on: Sequence[str],
    items_on: Sequence[UUID],
    seen_version: int,
) -> Published:
    """The person's hand-off (module docstring)."""
    from abacus.modules.closes.service import visible_close
    from abacus.modules.engagements.api import engagement_resource_of
    from abacus.modules.ledger.api import tb_handoff
    from abacus.modules.tax.api import handoff_target

    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(PUBLISH, "role")
    close = await visible_close(ctx, close_id)
    await authorise(ctx, PUBLISH, await engagement_resource_of(ctx.tenant, close.engagement_id))
    found = await availability(ctx, close_id)
    if found.status not in ("ready",) or found.target_return_id is None:
        raise HandoffNotAvailable(facts={"status": found.status})
    if seen_version != found.version:
        raise HandoffStale(facts={"version": found.version})
    year = int(close.period[:4])
    entity = cast(UUID, close.client_entity_id)
    tb = await _year_tb(ctx.tenant, entity, year)
    target = await handoff_target(ctx.tenant, entity, year)
    if tb is None or target is None:
        raise HandoffNotAvailable(facts={"status": "no_trial_balance"})
    chosen = [s for s in found.schedules if s.key in set(schedules_on)]
    toggled = {i.issue_id for i in found.items} & set(items_on)
    ref = f"{month_words(close.period)} close"
    items = [
        tb_handoff.TaxItem("close_issue", {"issue_id": str(i.issue_id), "ref": ref}, ZERO, True)
        for i in found.items
        if i.issue_id in toggled
    ]
    preview = tb_handoff.preview(
        [tb_handoff.AccountIn(c, n, b) for c, n, b in tb.accounts],
        prior_codes=await _prior_codes(ctx.tenant, close.engagement_id, year),
        suggestions={},
        book_income_before_tax=await book_income(
            ctx.tenant, close.engagement_id, year, tb.accounts
        ),
        income_tax_expense=ZERO, schedules=[s.key for s in chosen], tax_items=items,
    )  # fmt: skip
    from abacus.modules.organisations.api import client_of_entity

    client = await client_of_entity(ctx.tenant, entity)
    if client is None:
        raise HandoffNotAvailable(facts={"status": "no_client"})
    draft = tb_handoff.Draft(
        client_id=client, source_kind="close_lock", source_engagement_id=close.engagement_id,
        source_work_item_id=close_id, source_snapshot_id=tb.snapshot_id,
        target_work_item_id=target.return_id, preview=preview,
        schedule_facts={s.key: {k: str(v) for k, v in s.figures.items()} for s in chosen},
    )  # fmt: skip
    c12 = await tb_handoff.create(ctx.tenant, ctx.user_id, draft, preview.preview_hash)
    async with tenant_session(ctx.tenant) as session:
        prior = (await session.execute(_HANDOFFS, {"c": close_id})).all()
    previous = prior[-1] if prior else None
    recipients = sorted(
        {u for u in (target.preparer_user_id, target.reviewer_user_id) if u is not None}, key=str
    )
    async with uow(ctx.tenant) as tx:
        new_id = await tx.session.scalar(
            _INSERT,
            {"t": ctx.tenant_id, "c": close_id, "e": entity, "v": found.tb_version,
             "snap": tb.snapshot_id, "r": target.return_id, "engine": target.engine or "none",
             "s": json.dumps([{"key": s.key, "included": True,
                               "figures": {k: str(v) for k, v in s.figures.items()}}
                              for s in chosen]),
             "i": json.dumps([{"issue_id": str(i.issue_id),
                               "create_tax_issue": i.issue_id in toggled} for i in found.items]),
             "ref": c12, "by": ctx.user_id, "sup": None if previous is None else previous.id},
        )  # fmt: skip
        scope = Scope(engagement_id=close.engagement_id, work_item_id=close_id)
        tx.record(
            "tax_handoff.published",
            target=Target("tax_handoff", cast(UUID, new_id)),
            after=Ref(c12=c12, tax_return=target.return_id),
            scope=scope,
        )
        tx.emit(
            TaxHandoffPublished(
                tax_handoff_id=cast(UUID, new_id), close_id=close_id,
                tax_return_id=target.return_id, by_user=ctx.user_id,
                recipient_user_ids=recipients,
            )
        )  # fmt: skip
        if previous is not None:
            tx.emit(
                TaxHandoffSuperseded(
                    tax_handoff_id=cast(UUID, previous.id), close_id=close_id,
                    tax_return_id=target.return_id, by_user=ctx.user_id,
                    recipient_user_ids=recipients,
                )
            )  # fmt: skip
    return Published(cast(UUID, new_id), cast(str, found.tb_version), len(items), c12)


__all__ = [
    "SCHEDULES",
    "Availability",
    "HandoffNotAvailable",
    "HandoffStale",
    "Item",
    "Published",
    "Schedule",
    "ScheduleResult",
    "TaxHandoffPublished",
    "TaxHandoffSuperseded",
    "availability",
    "distributions_of",
    "gate",
    "month_words",
    "publish",
    "schedules",
    "tb_version",
]
