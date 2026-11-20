"""States and PTET (T-06-T36; TASK-8834; T-06 F4; SPEC-702; TXP-09 a to e, TXP-10; ADR-050,
ADR-005; DEC-5836). Amber.

- **Views** (`states.read`): apportionment (each state's share; the tally ties when the shares foot
  to 100.0 and no property lacks a state), credits (each partner's PTET credit by state) and nexus
  (each state's facts and conclusion).
- **Sourcing.** A person proposes the return's sourcing position (`sourcing.propose`): the row is
  `proposed` and the TXP-10 review point "Approve sourcing" is raised on the return (deduplicated
  on its source reference). A reviewer approves it (`sourcing.approve`: partner, manager or
  reviewer; never the agent or the system):
  the row is `approved` and the review point resolves as the system, once (a resolved issue stays
  resolved). Undo inside 10 seconds of the approval (DEC-24's window) writes `sourcing.undone`,
  a compensating event: the row moves to `undone`; after the window, 409 `undo_window_closed`.
- **PTET** (`ptet.update`): the election, and a payment (insert-only `ptet_payments`), on the
  election's version (409 `ptet_changed`). The amount is E9's (`compute.states.ptet`) from the
  stored base and the year's rate; partner credits split it by the ownership weights (largest
  remainder, DEC-77) into `ptet_partner_credits`. An elected state paid short raises the
  payment-gap issue (deduplicated); paying in full resolves it as the system. A property with no
  state raises the unmapped-factor issue the same way; mapping it resolves it.
- **TXP-12** reads each partner's state credit through `partner_state_credits` (Feld's 16,025).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.tax.compute import states as e9

READ: Final = "states.read"
PROPOSE: Final = "sourcing.propose"
APPROVE: Final = "sourcing.approve"
PTET: Final = "ptet.update"
UNDO_WINDOW: Final = timedelta(seconds=10)
METHOD: Final = "market_based_receipts"
TARGET: Final = "sourcing_position"
ZERO: Final = Decimal(0)
HUNDRED: Final = Decimal(100)
Ptet = Literal["elected", "recommend", "not_elected"]
Tally = Literal["tie", "off", "check"]


class UndoWindowClosed(DomainConflict):
    code = "undo_window_closed"


class PtetChanged(DomainConflict):
    code = "ptet_changed"


class SourcingNotPending(DomainConflict):
    code = "sourcing_not_pending"


def sourcing_ref(return_id: UUID) -> str:
    return f"sourcing:{return_id}"


def gap_ref(return_id: UUID, state: str) -> str:
    return f"ptet_gap:{return_id}:{state}"


def unmapped_ref(return_id: UUID) -> str:
    return f"unmapped_factor:{return_id}"


@dataclass(frozen=True)
class StateRow:
    state: str
    numerator: Decimal
    denominator: Decimal
    rate: Decimal | None
    status: str
    nexus_basis: str | None
    return_form: str | None
    share: Decimal
    ptet: Ptet
    ptet_amount: Decimal | None
    paid: Decimal | None
    paid_on: date | None
    mapped: bool
    nexus: str | None


@dataclass(frozen=True)
class NexusRow:
    state: str
    fact: str
    evidence_version_id: UUID | None
    conclusion: str


@dataclass(frozen=True)
class StatesView:
    nexus_rows: tuple[NexusRow, ...]
    partner_names: dict[UUID, str]
    states: tuple[StateRow, ...]
    tally: Tally
    sourcing: str | None
    paid_count: int
    payable_count: int
    credits: dict[UUID, dict[str, Decimal]]


_APPORTION: Final = text(
    "SELECT state, sum(numerator) AS numerator, max(denominator) AS denominator, "
    "max(nexus_basis) AS nexus_basis, max(return_form) AS return_form, "
    "bool_and(status = 'approved') AS approved FROM state_apportionments WHERE work_item_id = :r "
    "GROUP BY state ORDER BY state"
)
_ELECTIONS: Final = text(
    "SELECT state, election, amount, base, rate, version FROM ptet_elections "
    "WHERE work_item_id = :r"
)
_PAID: Final = text(
    "SELECT state, sum(amount) AS paid, max(paid_on) AS paid_on FROM ptet_payments "
    "WHERE work_item_id = :r GROUP BY state"
)
_NEXUS: Final = text(
    "SELECT state, fact, evidence_version_id, conclusion FROM nexus_facts WHERE work_item_id = :r "
    "ORDER BY state, id"
)
_UNMAPPED: Final = text(
    "SELECT count(*) FROM tax_properties WHERE work_item_id = :r AND state IS NULL "
    "AND use <> 'land_only'"
)
_SOURCING: Final = text(
    "SELECT id, status, decided_by, decided_at FROM sourcing_positions "
    "WHERE work_item_id = :r ORDER BY id DESC LIMIT 1"
)
_CREDITS: Final = text(
    "SELECT partner_id, state, amount FROM ptet_partner_credits WHERE work_item_id = :r"
)


async def _loaded(ctx: AuthContext, return_id: UUID) -> tuple[UUID, Any]:  # Any: a row value
    from abacus.modules.tax.overview import load_return, return_resource

    loaded = await load_return(ctx, return_id)
    return loaded.facts.engagement_id, await return_resource(ctx, loaded)


def _human(ctx: AuthContext, action: str) -> None:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(action, "role")


async def partner_state_credits(
    tenant: TenantContext, return_id: UUID
) -> dict[UUID, dict[str, Decimal]]:
    """Each partner's PTET credit by state (TXP-12's state K-1 column)."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_CREDITS, {"r": return_id})).all()
    out: dict[UUID, dict[str, Decimal]] = {}
    for r in rows:
        out.setdefault(UUID(str(r.partner_id)), {})[str(r.state)] = Decimal(r.amount)
    return out


async def view(ctx: AuthContext, return_id: UUID) -> StatesView:
    _engagement, resource = await _loaded(ctx, return_id)
    await authorise(ctx, READ, resource)
    async with tenant_session(ctx.tenant) as session:
        apportion = (await session.execute(_APPORTION, {"r": return_id})).all()
        elections = {str(e.state): e for e in await session.execute(_ELECTIONS, {"r": return_id})}
        paid = {str(p.state): p for p in await session.execute(_PAID, {"r": return_id})}
        nexus_rows = tuple(
            NexusRow(
                str(n.state),
                str(n.fact),
                None if n.evidence_version_id is None else UUID(str(n.evidence_version_id)),
                str(n.conclusion),
            )
            for n in await session.execute(_NEXUS, {"r": return_id})
        )
        names = {
            UUID(str(x.id)): str(x.display_name)
            for x in await session.execute(
                text("SELECT id, display_name FROM partners WHERE work_item_id = :r"),
                {"r": return_id},
            )
        }
        unmapped = int(await session.scalar(_UNMAPPED, {"r": return_id}) or 0)
        sourcing = (await session.execute(_SOURCING, {"r": return_id})).first()
    nexus = {n.state: n.conclusion for n in nexus_rows}
    rows: list[StateRow] = []
    for a in apportion:
        state = str(a.state)
        share = (Decimal(a.numerator) * HUNDRED / Decimal(a.denominator)).quantize(Decimal("0.1"))
        e = elections.get(state)
        p = paid.get(state)
        rows.append(
            StateRow(
                state,
                Decimal(a.numerator),
                Decimal(a.denominator),
                None if e is None or e.rate is None else Decimal(e.rate),
                "approved" if a.approved else "in_review",
                a.nexus_basis,
                a.return_form,
                share,
                cast(Ptet, "not_elected" if e is None else str(e.election)),
                None if e is None or e.amount is None else Decimal(e.amount),
                None if p is None else Decimal(p.paid),
                None if p is None else p.paid_on,
                unmapped == 0,
                nexus.get(state),
            )
        )
    total = sum((r.share for r in rows), ZERO)
    tally: Tally = "check" if unmapped else ("tie" if rows and total == HUNDRED else "off")
    payable = [r for r in rows if r.ptet == "elected" and r.ptet_amount]
    paid_full = [r for r in payable if (r.paid or ZERO) >= (r.ptet_amount or ZERO)]
    return StatesView(
        nexus_rows,
        names,
        tuple(rows), tally, None if sourcing is None else str(sourcing.status), len(paid_full),
        len(payable), await partner_state_credits(ctx.tenant, return_id),
    )  # fmt: skip


async def _raise(ctx: AuthContext, return_id: UUID, title: str, ref: str) -> UUID:
    from abacus.modules.review.api import create_issue

    return await create_issue(
        ctx, record_type="tax_return", record_id=return_id, kind="review_point",
        priority="medium", title=title, internal_note=None, client_wording=None,
        client_contact_id=None, assignee_user_id=None, assignee_agent=False, blocks=(),
        source_ref=ref, work_item_id=return_id,
    )  # fmt: skip


async def _resolve(tenant: TenantContext, ref: str) -> list[UUID]:
    from abacus.modules.review.api import system_resolve_dependents

    system = TenantContext(tenant.tenant_id, "system", "tax:states")
    return await system_resolve_dependents(system, ref)


async def unmapped_check(ctx: AuthContext, return_id: UUID) -> None:
    """The unmapped-factor issue, raised while a property has no state and resolved once mapped."""
    async with tenant_session(ctx.tenant) as session:
        unmapped = int(await session.scalar(_UNMAPPED, {"r": return_id}) or 0)
    if unmapped:
        await _raise(ctx, return_id, "A property has no state: map it before apportionment",
                     unmapped_ref(return_id))  # fmt: skip
    else:
        await _resolve(ctx.tenant, unmapped_ref(return_id))


async def propose_sourcing(ctx: AuthContext, return_id: UUID) -> UUID:
    _human(ctx, PROPOSE)
    engagement_id, resource = await _loaded(ctx, return_id)
    await authorise(ctx, PROPOSE, resource)
    async with uow(ctx.tenant) as tx:
        row_id = (
            await tx.session.execute(
                text(
                    "INSERT INTO sourcing_positions (tenant_id, engagement_id, work_item_id, "
                    "method) VALUES (:t, :e, :r, :m) RETURNING id"
                ),
                {"t": ctx.tenant_id, "e": engagement_id, "r": return_id, "m": METHOD},
            )
        ).scalar_one()
        tx.record(
            "sourcing.proposed",
            target=Target(TARGET, UUID(str(row_id))),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    await _raise(ctx, return_id, "Approve sourcing", sourcing_ref(return_id))
    await unmapped_check(ctx, return_id)
    return UUID(str(row_id))


async def latest_sourcing(tenant: TenantContext, return_id: UUID) -> Any:  # noqa: ANN401 -- a text row
    async with tenant_session(tenant) as session:
        return (await session.execute(_SOURCING, {"r": return_id})).first()


async def approve_sourcing(ctx: AuthContext, return_id: UUID) -> list[UUID]:
    """A reviewer's approval (module docstring); answers the issues it resolved (once)."""
    _human(ctx, APPROVE)
    engagement_id, resource = await _loaded(ctx, return_id)
    await authorise(ctx, APPROVE, resource)
    latest = await latest_sourcing(ctx.tenant, return_id)
    if latest is None or str(latest.status) != "proposed":
        raise SourcingNotPending(facts={"work_item_id": str(return_id)})
    async with uow(ctx.tenant) as tx:
        moved = await tx.session.scalar(
            text(
                "UPDATE sourcing_positions SET status = 'approved', decided_by = :u, "
                "decided_at = clock_timestamp() WHERE id = :i AND status = 'proposed' RETURNING id"
            ),
            {"u": ctx.user_id, "i": latest.id},
        )
        if moved is None:
            raise SourcingNotPending(facts={"work_item_id": str(return_id)})
        tx.record(
            "sourcing.approved",
            target=Target(TARGET, UUID(str(latest.id))),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )
    return await _resolve(ctx.tenant, sourcing_ref(return_id))


async def undo_sourcing(ctx: AuthContext, return_id: UUID) -> None:
    """Inside 10 seconds of the approval: `sourcing.undone`, the compensating event."""
    _human(ctx, APPROVE)
    engagement_id, resource = await _loaded(ctx, return_id)
    await authorise(ctx, APPROVE, resource)
    latest = await latest_sourcing(ctx.tenant, return_id)
    if latest is None or str(latest.status) != "approved" or latest.decided_at is None:
        raise SourcingNotPending(facts={"work_item_id": str(return_id)})
    if await now(ctx.tenant) - latest.decided_at > UNDO_WINDOW:
        raise UndoWindowClosed(facts={"seconds": int(UNDO_WINDOW.total_seconds())})
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE sourcing_positions SET status = 'undone' WHERE id = :i "
                "AND status = 'approved'"
            ),
            {"i": latest.id},
        )
        tx.record(
            "sourcing.undone",
            target=Target(TARGET, UUID(str(latest.id))),
            after=Ref(by=ctx.user_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=return_id),
        )


async def _weights(tenant: TenantContext, return_id: UUID) -> dict[str, Decimal]:
    """Period-weighted profit percentages by partner (the ownership periods, T-05-T41)."""
    from abacus.modules.tax.entity_partners import ownership

    found = await ownership(tenant, return_id)
    weights: dict[str, Decimal] = {}
    for p in found.periods:
        days = Decimal((p.ends_on - p.starts_on).days + 1)
        for partner, share in p.shares.items():
            weights[partner] = weights.get(partner, ZERO) + share * days
    return weights


async def update_ptet(
    ctx: AuthContext,
    return_id: UUID,
    state: str,
    *,
    election: Ptet,
    payment_amount: Decimal | None,
    payment_on: date | None,
    expected_version: int,
) -> int:
    """The election and a payment (module docstring); answers the election's new version."""
    from abacus.modules.tax.overview import tax_year_of

    _human(ctx, PTET)
    engagement_id, resource = await _loaded(ctx, return_id)
    await authorise(ctx, PTET, resource)
    async with tenant_session(ctx.tenant) as session:
        current = (
            await session.execute(
                text(
                    "SELECT version, base FROM ptet_elections WHERE work_item_id = :r "
                    "AND state = :s"
                ),
                {"r": return_id, "s": state},
            )
        ).first()
    if current is None:
        raise NotFound("ptet_election")
    if int(current.version) != expected_version:
        raise PtetChanged(facts={"version": int(current.version)})
    year = await tax_year_of(ctx.tenant, return_id)
    rate = e9.rate(year, state) if election == "elected" else None
    amount = (
        e9.ptet(Decimal(current.base), rate)
        if rate is not None and current.base is not None
        else None
    )
    weights = await _weights(ctx.tenant, return_id) if amount else {}
    credits = e9.partner_credits(amount, weights) if amount and weights else {}
    scope = Scope(engagement_id=engagement_id, work_item_id=return_id)
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text(
                "UPDATE ptet_elections SET election = :el, rate = :rate, amount = :amt, "
                "version = version + 1 WHERE work_item_id = :r AND state = :s AND version = :v"
            ),
            {
                "el": election,
                "rate": rate,
                "amt": amount,
                "r": return_id,
                "s": state,
                "v": expected_version,
            },
        )
        if payment_amount is not None and payment_on is not None:
            await tx.session.execute(
                text(
                    "INSERT INTO ptet_payments (tenant_id, engagement_id, work_item_id, state, "
                    "paid_on, amount, recorded_by) VALUES (:t, :e, :r, :s, :on, :a, :by)"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "r": return_id,
                    "s": state,
                    "on": payment_on,
                    "a": payment_amount,
                    "by": ctx.user_id,
                },
            )
        for partner, credit in credits.items():
            await tx.session.execute(
                text(
                    "INSERT INTO ptet_partner_credits (tenant_id, engagement_id, work_item_id, "
                    "partner_id, state, amount, rounding_rule) VALUES (:t, :e, :r, :p, :s, :a, "
                    "'largest_remainder') ON CONFLICT (work_item_id, partner_id, state) DO UPDATE "
                    "SET amount = EXCLUDED.amount"
                ),
                {
                    "t": ctx.tenant_id,
                    "e": engagement_id,
                    "r": return_id,
                    "p": UUID(partner),
                    "s": state,
                    "a": credit,
                },
            )
        tx.record(
            "ptet.updated", target=Target("ptet_election", return_id), after=Ref(state=state),
            scope=scope,
        )  # fmt: skip
    async with tenant_session(ctx.tenant) as session:
        paid = Decimal(
            await session.scalar(
                text(
                    "SELECT coalesce(sum(amount), 0) FROM ptet_payments WHERE work_item_id = :r "
                    "AND state = :s"
                ),
                {"r": return_id, "s": state},
            )
            or 0
        )
    gaps = e9.payment_gaps(
        {state: amount} if election == "elected" and amount else {}, {state: paid}
    )
    if gaps:
        await _raise(
            ctx, return_id, f"{state} PTET is not paid in full", gap_ref(return_id, state)
        )
    else:
        await _resolve(ctx.tenant, gap_ref(return_id, state))
    return expected_version + 1


__all__ = [
    "PtetChanged",
    "StatesView",
    "UndoWindowClosed",
    "approve_sourcing",
    "partner_state_credits",
    "propose_sourcing",
    "undo_sourcing",
    "unmapped_check",
    "update_ptet",
    "view",
]
