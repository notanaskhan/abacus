"""The synthetic-only entity return recorder (T-05-T45; T-05 §5.3; DEC-4711). Amber. The scenario
loader's one way to put an entity return's facts in place for the Brightwater Hale tenant
(Ridgeline and Harborview), through this module's own tables and `workbook_service.write_cells`
(review's versions). It refuses every firm that is not synthetic (404, as `workspace_seed`), so
nothing it writes can stand in for a real return.

What it records: the entity profile, the partners, their ownership periods and the interest
transfers (idempotent: a row that exists is left as it is), and the workbook cells a run left
(the trial balance on 01 with AJE and TJE, 05 Capital, 06 Schedule K, 07 M-2, 08 and 09), each as
`engine_import` with a citation note naming the scenario, written once (a workbook with cells is
not rewritten). Allocation structures, sign-offs and runs go through their own services (the
allocation service, P-04, the run recorder): the loader calls them.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.engagements.api import work_item_engagement
from abacus.modules.identity.api import AuthContext, is_synthetic_firm
from abacus.modules.review.api import current_values
from abacus.modules.tax.workbook_service import WORKBOOK, CellWrite, write_cells

# A citation, never firm display text: the firm is the tenant the loader names (P-08-T22 T14).
NOTE: Final = "Synthetic scenario (seed)"


@dataclass(frozen=True)
class SeedPartner:
    name: str
    kind: str  # gp, lp
    entity_kind: str  # individual, llc, partnership
    ord: int
    periods: Sequence[tuple[date, date, Decimal]] = ()  # (from, to, profit %)
    admitted_on: date | None = None


@dataclass(frozen=True)
class SeedTransfer:
    on: date
    from_partner: str
    to_partner: str
    points: Decimal
    price: Decimal | None = None


@dataclass(frozen=True)
class SeedEntity:
    principal_activity: str
    business_code: str
    accounting_method: str
    books_basis: str
    partners: Sequence[SeedPartner]
    transfers: Sequence[SeedTransfer] = ()
    cells: Sequence[tuple[str, Decimal | str]] = field(default_factory=tuple)


_PROFILE: Final = text(
    "INSERT INTO entity_return_profiles (tenant_id, engagement_id, work_item_id, "
    "principal_activity, business_code, accounting_method, books_basis, ledger_source) "
    "VALUES (:t, :e, :r, :activity, :code, :method, :basis, 'file') "
    "ON CONFLICT (work_item_id) DO NOTHING"
)
_PARTNER: Final = text(
    "INSERT INTO partners (tenant_id, engagement_id, work_item_id, kind, display_name, "
    "entity_kind, admitted_on, ord) VALUES (:t, :e, :r, :kind, :name, :ek, :admitted, :ord) "
    "ON CONFLICT (work_item_id, display_name) DO NOTHING"
)
_PARTNER_ID: Final = text(
    "SELECT id FROM partners WHERE work_item_id = :r AND display_name = :name"
)
_PERIOD: Final = text(
    "INSERT INTO ownership_periods (tenant_id, engagement_id, work_item_id, partner_id, "
    "period_from, period_to, profit_pct, loss_pct, capital_pct) VALUES (:t, :e, :r, :p, :f, :to, "
    ":pct, :pct, :pct) ON CONFLICT (partner_id, period_from) DO NOTHING"
)
_TRANSFER_EXISTS: Final = text(
    "SELECT 1 FROM interest_transfers WHERE work_item_id = :r AND transfer_date = :on "
    "AND from_partner_id = :f AND to_partner_id = :to"
)
_TRANSFER: Final = text(
    "INSERT INTO interest_transfers (tenant_id, engagement_id, work_item_id, transfer_date, "
    "from_partner_id, to_partner_id, points, price) VALUES (:t, :e, :r, :on, :f, :to, :points, "
    ":price)"
)


async def record_synthetic_entity(
    ctx: AuthContext, return_id: UUID, entity: SeedEntity
) -> dict[str, UUID]:
    """The return's entity facts as the scenario names them; answers the partners' ids by name."""
    if not await is_synthetic_firm(ctx.tenant):
        raise NotFound("tax_return")
    engagement_id = await work_item_engagement(ctx.tenant, return_id)
    if engagement_id is None:
        raise NotFound("tax_return")
    scope = {"t": ctx.tenant_id, "e": engagement_id, "r": return_id}
    ids: dict[str, UUID] = {}
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            _PROFILE,
            {
                **scope,
                "activity": entity.principal_activity,
                "code": entity.business_code,
                "method": entity.accounting_method,
                "basis": entity.books_basis,
            },
        )
        for p in entity.partners:
            await tx.session.execute(
                _PARTNER,
                {
                    **scope, "kind": p.kind, "name": p.name, "ek": p.entity_kind,
                    "admitted": p.admitted_on, "ord": p.ord,
                },
            )  # fmt: skip
            pid = await tx.session.scalar(_PARTNER_ID, {"r": return_id, "name": p.name})
            ids[p.name] = pid
            for start, end, pct in p.periods:
                await tx.session.execute(
                    _PERIOD, {**scope, "p": pid, "f": start, "to": end, "pct": pct}
                )
        for t in entity.transfers:
            args = {"r": return_id, "on": t.on, "f": ids[t.from_partner], "to": ids[t.to_partner]}
            if await tx.session.scalar(_TRANSFER_EXISTS, args) is None:
                await tx.session.execute(
                    _TRANSFER, {**scope, **args, "points": t.points, "price": t.price}
                )
        tx.record(
            "tax_entity.recorded_synthetic",
            target=Target(WORKBOOK, return_id),
            after=Ref(partners=len(entity.partners), transfers=len(entity.transfers)),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    if entity.cells and not await current_values(ctx.tenant, WORKBOOK, return_id):
        async with uow(ctx.tenant) as tx:
            await write_cells(
                tx,
                engagement_id=engagement_id,
                return_id=return_id,
                writes=[
                    CellWrite(address, value, "engine_import", citation_note=NOTE)
                    for address, value in entity.cells
                ],
            )
            tx.record(
                "workbook.step_written",
                target=Target(WORKBOOK, return_id),
                after=Ref(cells=len(entity.cells), synthetic=True),
                scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
            )
    return ids


__all__ = ["SeedEntity", "SeedPartner", "SeedTransfer", "record_synthetic_entity"]
