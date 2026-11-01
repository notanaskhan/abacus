"""Due dates and BH-TAX-02 on the return (T-02-T10; T-02 §3, §4.2; TAX-01, TAX-02, TXP-12;
C21 `as_of`: the period end).

- On create, and whenever the extension changes, a return's original and extended due dates
  come from the registered due-dates source (practice registers `due_dates_for`: K-02's
  published rules, IRC §7503 roll; tax never imports that edge module, T08), with the
  reference-set version ids pinned beside them; its approval policy (the firm's
  `return_approval_policy`, BH-TAX-02) is pinned once, at creation, from `methodology.api`.
- A return whose dates no published rule answers keeps them empty (creation never fails on a
  missing rule); the board shows "—".
- A published correction recomputes every unfiled return (`recompute_unfiled`, on
  `reference_set.published`); a filed or accepted return keeps the dates it was filed on.
- `rule_texts` gives the Due popover its rule ("15th day, 3rd month + 6 months") per form.

The tax form codes map to the rule rows' forms (`FORM_FOR_RULES`; the TPL-01 mapping test).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Protocol
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import OutboxEvent, Ref, Target, UnitOfWork, uow
from abacus.modules.methodology.api import current_version_of_kind


class DueDates(Protocol):
    """What a due-dates source answers (`practice.api.DueDates` has these and more)."""

    @property
    def original_due_on(self) -> date: ...
    @property
    def extended_due_on(self) -> date | None: ...
    @property
    def reference_set_version_ids(self) -> Sequence[UUID]: ...
    @property
    def rule_text(self) -> str | None: ...
    @property
    def extended_rule_text(self) -> str | None: ...


# (form, tax year, period end) -> the dates; `LookupError` when no published rule answers.
DueDatesSource = Callable[[str, int, date], Awaitable[DueDates]]
_SOURCE: list[DueDatesSource] = []


def register_due_dates_source(source: DueDatesSource) -> None:
    """Practice registers its rule engine once; a second, different source is a mistake."""
    if _SOURCE and _SOURCE[0] is not source:
        raise ValueError("a due-dates source is already registered")
    _SOURCE[:] = [source]


async def due_dates_for(form: str, tax_year: int, period_end: date) -> DueDates:
    if not _SOURCE:
        raise LookupError("no due-dates source is registered")
    return await _SOURCE[0](form, tax_year, period_end)


# The return's form code (0089, 0403) as C21's due-date rows name it.
FORM_FOR_RULES: Final[Mapping[str, str]] = {
    "1040": "1040",
    "1040x": "1040",
    "1041": "1041",
    "1065": "1065",
    "1120s": "1120-S",
    "1120": "1120",
    "990": "990",
    "706": "706",
    "709": "709",
}
_FILED: Final = ("filed", "accepted")

_READ = text(
    "SELECT form, tax_year, fiscal_year_end, extended, status, approval_policy_version_id "
    "FROM tax_returns WHERE work_item_id = :work_item_id FOR UPDATE"
)
_PIN = text(
    "UPDATE tax_returns SET original_due_on = :original, extended_due_on = :extended_on, "
    "due_rule_version_ids = CAST(:versions AS jsonb), "
    "approval_policy_version_id = coalesce(approval_policy_version_id, :policy) "
    "WHERE work_item_id = :work_item_id"
)
_EXTENDED = text(
    "UPDATE tax_returns SET extended = :extended, row_version = row_version + 1 "
    "WHERE work_item_id = :work_item_id AND status NOT IN ('filed', 'accepted')"
)
_UNFILED = text(
    "SELECT work_item_id FROM tax_returns WHERE status NOT IN ('filed', 'accepted') "
    "ORDER BY work_item_id"
)


@dataclass(frozen=True)
class Pinned:
    original_due_on: date | None
    extended_due_on: date | None
    reference_set_version_ids: tuple[UUID, ...]
    approval_policy_version_id: UUID | None


def period_end(tax_year: int, fiscal_year_end: date | None) -> date:
    return fiscal_year_end or date(tax_year, 12, 31)


async def dates_for(form: str, tax_year: int, fiscal_year_end: date | None) -> DueDates | None:
    rules_form = FORM_FOR_RULES.get(form)
    if rules_form is None:
        return None
    try:
        return await due_dates_for(rules_form, tax_year, period_end(tax_year, fiscal_year_end))
    except LookupError:
        return None


async def pin(session: AsyncSession, tenant: TenantContext, work_item_id: UUID) -> Pinned | None:
    """Recompute and store one return's dates (in the caller's transaction); a filed or
    accepted return is left as it was filed. None when there is no such return."""
    row = (await session.execute(_READ, {"work_item_id": work_item_id})).first()
    if row is None:
        return None
    form, tax_year, fye, extended, status, policy = row
    if status in _FILED:
        return None
    found = await dates_for(str(form), int(tax_year), fye)
    if policy is None:
        ref = await current_version_of_kind(
            tenant.tenant_id, "return_approval_policy", await today(tenant)
        )
        policy = None if ref is None else ref.version_id
    original = None if found is None else found.original_due_on
    extended_on = found.extended_due_on if found is not None and extended else None
    versions = () if found is None else tuple(found.reference_set_version_ids)
    await session.execute(
        _PIN,
        {
            "work_item_id": work_item_id,
            "original": original,
            "extended_on": extended_on,
            "versions": json.dumps([str(v) for v in versions]),
            "policy": policy,
        },
    )
    return Pinned(original, extended_on, versions, policy)


def _day(on: date | None) -> int:
    """A date as an audit ref (integers only): 2026-09-15 is 20260915; none is 0."""
    return 0 if on is None else on.year * 10000 + on.month * 100 + on.day


def record_pinned(tx: UnitOfWork, work_item_id: UUID, pinned: Pinned) -> None:
    tx.record(
        "tax_return.due_dates_pinned",
        target=Target("work_item", work_item_id),
        after=Ref(
            original=_day(pinned.original_due_on),
            extended=_day(pinned.extended_due_on),
            rules=len(pinned.reference_set_version_ids),
        ),
    )


async def set_extended(
    tx: UnitOfWork, tenant: TenantContext, work_item_id: UUID, extended: bool
) -> Pinned | None:
    """An extension filed or withdrawn (the caller authorised it): the flag, then the dates."""
    await tx.session.execute(_EXTENDED, {"work_item_id": work_item_id, "extended": extended})
    pinned = await pin(tx.session, tenant, work_item_id)
    if pinned is not None:
        record_pinned(tx, work_item_id, pinned)
    return pinned


async def recompute_unfiled(tenant: TenantContext) -> int:
    """Every unfiled return's dates again (a published correction), each in its own unit of
    work with its audit event; how many were recomputed."""
    async with tenant_session(tenant) as session:
        ids = list((await session.execute(_UNFILED)).scalars())
    done = 0
    for work_item_id in ids:
        async with uow(tenant) as tx:
            pinned = await pin(tx.session, tenant, work_item_id)
            if pinned is not None:
                record_pinned(tx, work_item_id, pinned)
                done += 1
    return done


async def on_reference_set_published(event: OutboxEvent) -> None:
    """K-02-T12's fan-out names the tenant; recompute is idempotent."""
    await recompute_unfiled(TenantContext(event.tenant_id, "system", "tax:due_dates"))


async def rule_texts(tax_year: int) -> dict[str, tuple[str | None, str | None]]:
    """Per tax form code: the rule text, original and extended (calendar-year period end)."""
    out: dict[str, tuple[str | None, str | None]] = {}
    for form in FORM_FOR_RULES:
        found = await dates_for(form, tax_year, None)
        out[form] = (None, None) if found is None else (found.rule_text, found.extended_rule_text)
    return out


__all__ = [
    "FORM_FOR_RULES",
    "Pinned",
    "dates_for",
    "on_reference_set_published",
    "period_end",
    "pin",
    "recompute_unfiled",
    "record_pinned",
    "rule_texts",
    "set_extended",
]
