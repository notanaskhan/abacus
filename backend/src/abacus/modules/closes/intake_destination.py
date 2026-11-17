"""The `close_receipt` intake destination (C-01-T58; N-01 DV-7; INB-02 b; DEC-5414; amber).

N-01's triage picker (`communications.api.register_intake_destination`) lists, under a client:

- each **open close** of the client (not delivered or locked) as a `close_receipt` node: filing
  to it places the file on the close (its documents, CLS-03's intake);
- under a close, its **open close-intake requests** as `request` nodes (communications' own
  request placement fulfils the item, so the file lands in the close's intake binder, CLS-03);
- and the period's **card charges** from the C9 v2.1 register (credit-card accounts, the newest
  first) as information beside them: the receipt's candidates, not destinations (a charge is a
  ledger line, never a filing target; matching the receipt to one is the person's act on CLS-05).

Fails closed: with `closes.engine` off the destination lists nothing and places nothing (404),
so INB-02 keeps the request destinations. Only a person files (an agent or the system is refused
here as well as at the triage matrix and the decisions table's CHECK).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel._flags import CLOSES_ENGINE
from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import UnitOfWork
from abacus.modules.closes import repository as repo
from abacus.modules.communications.api import (
    IntakeDestination,
    IntakeNode,
    register_intake_destination,
)
from abacus.modules.communications.api import Placement as IntakePlacement
from abacus.modules.engagements.api import client_of
from abacus.modules.identity.api import AuthContext, Forbidden

KIND: Final = "close_receipt"
CHARGE_REASON: Final = "card_charge_candidate"
MAX_CHARGES: Final = 5
OPEN_REQUESTS: Final = frozenset({"requested", "returned"})  # requests.binders.OPEN_REQUEST
_NS: Final = uuid.UUID("7b0f6a52-4d2e-4f0e-9c1a-2f2f6c0c5e58")
_MONTHS: Final = (
    "January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December",
)  # fmt: skip

_OPEN_CLOSES: Final = text(
    "SELECT work_item_id, engagement_id, period, client_entity_id FROM closes "
    "WHERE status IN ('not_started', 'in_progress', 'in_review') AND locked_at IS NULL "
    "ORDER BY period DESC"
)


def _label(period: str) -> str:
    year, month = (int(x) for x in period.split("-"))
    return f"{_MONTHS[month - 1]} {year} close"


def charge_id(close_id: UUID, line_ref: str) -> UUID:
    """A stable id for an information node (never placed)."""
    return uuid.uuid5(_NS, f"{close_id}:{line_ref}")


def charge_label(payee: str | None, memo: str | None, on: str, amount: Decimal) -> str:
    who = (payee or memo or "Card charge").strip()[:80]
    return f"{who} · {on} · {abs(amount):,.2f}"


async def _person(ctx_or_tenant: AuthContext | TenantContext) -> bool:
    tenant = ctx_or_tenant if isinstance(ctx_or_tenant, TenantContext) else ctx_or_tenant.tenant
    return tenant.actor_kind == "human"


async def _client_closes(ctx: AuthContext, client_id: UUID) -> list[repo.CloseRow]:
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(_OPEN_CLOSES)).all()
        out: list[repo.CloseRow] = []
        for r in rows:
            if await client_of(ctx.tenant, r.engagement_id) != client_id:
                continue
            close = await repo.close_row(session, r.work_item_id)
            if close is not None:
                out.append(close)
    return out


async def _requests(ctx: AuthContext, close_id: UUID) -> list[IntakeNode]:
    from abacus.modules.requests.api import close_intake_binder, intake_items

    async with tenant_session(ctx.tenant) as session:
        binder = await close_intake_binder(session, close_id)
        if binder is None:
            return []
        items = await intake_items(session, binder.id, await today(ctx.tenant))
    return [
        IntakeNode("request", i.request_item_id, i.title[:200])
        for i in items
        if i.status in OPEN_REQUESTS
    ]


async def _charges(ctx: AuthContext, close: repo.CloseRow) -> list[IntakeNode]:
    from abacus.modules.ledger.api import PeriodNotAvailable, account_tree, register_lines

    if close.client_entity_id is None:
        return []
    try:
        tree = await account_tree(ctx.tenant, close.client_entity_id, close.period)
    except PeriodNotAvailable:
        return []
    cards = [a for a in tree.accounts if a.account_type == "Credit Card"]
    found: list[tuple[str, IntakeNode]] = []
    for account in cards:
        rows, _ = await register_lines(
            ctx.tenant, close.client_entity_id, account.external_id, close.period
        )
        for r in rows:
            if r.amount == 0:
                continue
            on = r.txn_date.isoformat()
            found.append(
                (
                    on,
                    IntakeNode(
                        KIND,
                        charge_id(close.work_item_id, r.line_ref),
                        charge_label(r.payee, r.memo, on, r.amount),
                        selectable=False,
                        reason_code=CHARGE_REASON,
                    ),
                )
            )
    found.sort(key=lambda x: x[0], reverse=True)
    return [n for _, n in found[:MAX_CHARGES]]


async def close_receipt_nodes(
    ctx: AuthContext, client_id: UUID, parent: UUID | None
) -> Sequence[IntakeNode]:
    """The client's open closes; under one, its open intake requests and card charges."""
    if not await _person(ctx) or not await flag_enabled(ctx.tenant, CLOSES_ENGINE):
        return []
    closes = await _client_closes(ctx, client_id)
    if parent is None:
        return [
            IntakeNode(KIND, c.work_item_id, _label(c.period), has_children=True) for c in closes
        ]
    close = next((c for c in closes if c.work_item_id == parent), None)
    if close is None:
        return []
    return [*await _requests(ctx, close.work_item_id), *await _charges(ctx, close)]


async def place_close_receipt(
    tenant: TenantContext, tx: UnitOfWork, close_id: UUID
) -> IntakePlacement:
    """Filing onto a close: its engagement and work item (CLS-03's intake)."""
    if not await _person(tenant):
        raise Forbidden("inbox.file", "role")
    if not await flag_enabled(tenant, CLOSES_ENGINE):
        raise NotFound(CLOSES_ENGINE.name)
    close = await repo.close_row(tx.session, close_id)
    if close is None or close.status in ("delivered", "locked"):
        raise NotFound("close")
    client = await client_of(tenant, close.engagement_id)
    if client is None:
        raise NotFound("close")
    return IntakePlacement(close.engagement_id, close.work_item_id, client)


def register() -> None:
    register_intake_destination(IntakeDestination(KIND, close_receipt_nodes, place_close_receipt))


__all__ = [
    "CHARGE_REASON",
    "KIND",
    "charge_id",
    "charge_label",
    "close_receipt_nodes",
    "place_close_receipt",
    "register",
]
